import sys, json
sys.path[:0]=['core','conditions','rules','libs','tools','sources']
from smartreact_engine import SmartReactEngine
e = SmartReactEngine()
print('triple note:', e.triple_template_note)
print('n triple templates:', len(e.triple_templates))
print('max_triples:', e.max_triples)
sm = [t[0] for t in e.triple_templates[:2]]
print('sample smarts:', [s[:110] for s in sm])
