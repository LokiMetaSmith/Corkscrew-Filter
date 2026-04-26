import yaml
from optimizer.llm_agent import LLMAgent

with open('configs/corkscrew_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

agent = LLMAgent(None)
params_def = config['geometry']['parameters']

# Test it with a dict containing malformed constants!
res = agent._generate_random_parameters(config['geometry']['parameters'], params_def)
print(res)
