from .utils import *
from .network_heads import *

def A2C(parclass):
  """Requires parent class, inherited from Agent."""
    
  class A2C(parclass):
    """
    Advantage Actor-Critic algorithm (A2C).
    Requires parent class inherited from Agent.
    Based on: https://arxiv.org/abs/1602.01783
    
    Args:
        FeatureExtractorNet - class inherited from nn.Module
        ActorCriticHead - class of Actor-Critic network head, ActorCriticHead or SeparatedActorCriticHead
        magnitude_logging_fraction - number of frames between magnitude logging (it's expensive to do each iteration), int
        rollout - number of frames for one iteration of updating NN weights
        gamma - infinite horizon protection, float, from 0 to 1
        entropy_loss_weight - weight of additional entropy loss
        critic_loss_weight - weight of critic loss
        optimizer - class inherited from torch.optimizer, Adam by default
        optimizer_args - arguments for optimizer, dictionary
        grad_norm_max - maximum of gradient norm
    """
    __doc__ += parclass.__doc__
    
    def __init__(self, config):
        super().__init__(config)
        self.gamma = config.get("gamma", 0.99)
        self.critic_loss_weight = config.get("critic_loss_weight", 1)
        self.entropy_loss_weight = config.get("entropy_loss_weight", 0)
        self.rollout = config.get("rollout", 5)
        self.grad_norm_max = config.get("grad_norm_max", None)
        self.magnitude_logging_fraction = config.get("magnitude_logging_fraction", 1000)
        
        self.policy = self.init_network()
        self.optimizer = config.get("optimizer", optim.Adam)(self.policy.parameters(), **config.get("optimizer_args", {}))
        
        self.observations = Tensor(size=(self.rollout + 1, self.env.num_envs, *config["observation_shape"])).zero_()
        self.rewards = Tensor(size=(self.rollout, self.env.num_envs, 1)).zero_()
        self.actions = LongTensor(size=(self.rollout + 1, self.env.num_envs, 1)).zero_()
        self.dones = Tensor(size=(self.rollout + 1, self.env.num_envs, 1)).zero_()
        self.returns = Tensor(size=(self.rollout + 1, self.env.num_envs, 1)).zero_()
        self.step = 0
        
        self.logger_labels["actor_loss"] = ("training iteration", "loss")
        self.logger_labels["critic_loss"] = ("training iteration", "loss")
        self.logger_labels["entropy_loss"] = ("training iteration", "loss")
        if self.config.get("linear_layer", nn.Linear) is NoisyLinear:
            self.logger_labels["magnitude"] = ("training epoch", "noise magnitude")
            
    def init_network(self):
        '''create a new ActorCritic-network'''
        net = self.config.get("ActorCriticHead", ActorCriticHead)(self.config)        
        net.after_init()
        return net

    def act(self, s):
        if self.is_learning:
            self.policy.train()
        else:
            self.policy.eval()
        
        with torch.no_grad():
            dist, values = self.policy(Tensor(s))
            actions = dist.sample().view(-1, 1)

        return actions.view(-1).cpu().numpy()
    
    def see(self, state, action, reward, next_state, done):
        super().see(state, action, reward, next_state, done)
        
        self.observations[self.step].copy_(Tensor(state))
        self.observations[self.step + 1].copy_(Tensor(next_state))
        self.actions[self.step].copy_(LongTensor(action).view(-1, 1))
        self.rewards[self.step].copy_(Tensor(reward).view(-1, 1))
        self.dones[self.step + 1].copy_(Tensor(done.astype(np.float32)).view(-1, 1))
        
        self.step = (self.step + 1) % self.rollout        
        if self.step == 0:
            self.update()
                
        if (self.frames_done % self.magnitude_logging_fraction < self.env.num_envs and
            self.config.get("linear_layer", nn.Linear) is NoisyLinear):         # TODO and if it is subclass?
            self.logger["magnitude"].append(self.policy.magnitude())
    
    def compute_returns(self, values):
        '''
        Fills self.returns using self.rewards, self.dones
        input: values, Tensor, num_steps + 1 x num_processes x 1
        '''
        self.returns[-1] = values[-1]
        for step in reversed(range(self.rewards.size(0))):
            self.returns[step] = self.returns[step + 1] * self.gamma * (1 - self.dones[step + 1]) + self.rewards[step]
    
    def update(self):
        """One step of optimization based on rollout memory"""
        self.policy.train()
        
        obs_shape = self.observations.size()[2:]
        num_steps, num_processes, _ = self.rewards.size()
        
        dist, values = self.policy(self.observations.view(-1, *obs_shape))
        action_log_probs = dist.log_prob(self.actions.view(-1))
        dist_entropy = dist.entropy()[:-1].mean()

        values = values.view(num_steps + 1, num_processes, 1)
        action_log_probs = action_log_probs.view(num_steps + 1, num_processes, 1)[:-1]    

        self.compute_returns(values)

        advantages = self.returns[:-1].detach() - values[:-1]
        critic_loss = advantages.pow(2).mean()
        actor_loss = -(advantages.detach() * action_log_probs).mean()

        loss = actor_loss + self.critic_loss_weight * critic_loss - self.entropy_loss_weight * dist_entropy

        self.optimizer.zero_grad()
        loss.backward()
        if self.grad_norm_max is not None:
            torch.nn.utils.clip_grad_norm_(self.policy.parameters(), self.grad_norm_max)
        self.optimizer.step()
        
        self.logger["actor_loss"].append(actor_loss.item())
        self.logger["critic_loss"].append(critic_loss.item())
        self.logger["entropy_loss"].append(dist_entropy.item())
    
    def load(self, name, *args, **kwargs):
        super().load(name, *args, **kwargs)
        self.policy.load_state_dict(torch.load(name + "-net"))

    def save(self, name, *args, **kwargs):
        super().save(name, *args, **kwargs)
        torch.save(self.policy.state_dict(), name + "-net")
  return A2C
