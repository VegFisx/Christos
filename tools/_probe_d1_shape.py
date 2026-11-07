import sys, json
sys.path[:0]=['core','conditions','rules','libs']
import direction as D
from model import Conditions
c=Conditions(solvent='water', temperature=100.0, time_min=60.0, pH=7.0)
c2=Conditions(solvent='toluene', temperature=100.0, time_min=60.0, pH=7.0)
for cls in ['mined_extra','mined_mono']:
    a=D.judge(cls, c, co_products=('O',)); b=D.judge(cls, c)
    print(json.dumps({'cls':cls,'water+O':[a['label'],a['source']],'water+none':[b['label'],b['source']]}, ensure_ascii=True))
