import sys, json
sys.path[:0]=['core','conditions','rules','libs']
import direction as D
from model import Conditions
c=Conditions(solvent='water', temperature=100.0, time_min=60.0, pH=7.0)
c2=Conditions(solvent='toluene', temperature=100.0, time_min=60.0, pH=7.0)
cases=[('dehydration',(-1,-2,-1)),('hydrolysis',(0,2,1)),('neutral',(0,0,0)),('bad',None)]
for nm,ed in cases:
    a=D.judge('mined_mono', c, element_delta=ed)
    b=D.judge('mined_mono', c2, element_delta=ed)
    print(json.dumps({'case':nm,'water':[a['label'],a['source']],'tol':[b['label'],b['source']]},ensure_ascii=True))
