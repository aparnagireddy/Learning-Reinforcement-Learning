from .DQN import *

def TargetQAgent(parclass):
  """Requires parent class, inherited from Agent"""   
    
  class TargetQAgent(parclass):
    '''
    Target network heuristic implementation.
    
    Args:
        target_update - frequency in frames of updating target network
    '''
    __doc__ += parclass.__doc__
    PARAMS = parclass.PARAMS | {"target_update"}
    
    def __init__(self, config):
        super().__init__(config)

        self.target_net = self.config.QnetworkHead(self.config, "Qnetwork").to(device)  # It is not correct for DDPG.
        self.unfreeze()

        self.config.setdefault("target_update", 100)

    def unfreeze(self):
        '''copy policy net weights to target net'''
        self.target_net.load_state_dict(self.q_net.state_dict())

    def see(self, state, action, reward, next_state, done):
        super().see(state, action, reward, next_state, done)

        if self.frames_done % self.config.target_update < self.env.num_envs:
            self.unfreeze()
    
    def estimate_next_state(self, next_state_b):
        return self.target_net.value(self.target_net(next_state_b))

    def load(self, name, *args, **kwargs):
        super().load(name, *args, **kwargs)
        self.unfreeze()
  return TargetQAgent
