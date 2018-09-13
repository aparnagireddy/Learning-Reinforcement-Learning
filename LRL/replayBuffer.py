from .agent import *

class ReplayBufferAgent(Agent):
    """
    Replay Memory storing all transitions seen with basic uniform batch sampling.
    Based on: https://arxiv.org/abs/1312.5602
    
    Args:
        replay_buffer_capacity - size of buffer, int
    """
    __doc__ += Agent.__doc__
    
    def __init__(self, replay_buffer_capacity=100000, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.replay_buffer_capacity = replay_buffer_capacity
        self.replay_buffer_nsteps = 1
        self.buffer = []
        self.pos = 0
    
    def memorize(self, state, action, reward, next_state, done, died):
        """Remember transition"""
        state      = np.expand_dims(state, 0)
        next_state = np.expand_dims(next_state, 0)
        
        if len(self) < self.replay_buffer_capacity:
            self.buffer.append((state, action, reward, next_state, done))
        else:
            self.buffer[self.pos] = (state, action, reward, next_state, done)
        
        self.pos = (self.pos + 1) % self.replay_buffer_capacity
        
    def see(self, state, action, reward, next_state, done, died):
        self.memorize(state, action, reward, next_state, done, died)       
        super().see(state, action, reward, next_state, done, died)
    
    def sample(self, batch_size):
        """
        Generate batch of given size.
        Output: state_batch - batch_size x state_dim 
        Output: action_batch - batch_size
        Output: reward_batch - batch_size
        Output: next_state_batch - batch_size x state_dim 
        Output: done_batch - batch_size
        Output: weights_batch - batch_size
        """
        state, action, reward, next_state, done = zip(*random.sample(self.buffer, batch_size))
        return np.concatenate(state), action, reward, np.concatenate(next_state), done, np.ones((batch_size))
    
    def update_priorities(self, batch_priorities):
        pass
    
    def __len__(self):
        return len(self.buffer)
    
    def read_memory(self, mem_f):
        self.buffer = pickle.load(mem_f)
        self.pos = pickle.load(mem_f)
    
    def write_memory(self, mem_f):
        pickle.dump(self.buffer, mem_f)
        pickle.dump(self.pos, mem_f)
    
    def save(self, name, save_replay_memory=False):
        super().save(name)
        
        if save_replay_memory:
            mem_f = open(name + "-memory", 'wb')
            self.write_memory(mem_f)
            mem_f.close() 
        
    def load(self, name, load_replay_memory=False):
        super().load(name)
        
        if load_replay_memory:
            mem_f = open(name + "-memory", 'rb')
            self.read_memory(mem_f)
            mem_f.close()
            
