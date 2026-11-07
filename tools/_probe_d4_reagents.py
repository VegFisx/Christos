import sys
sys.path[:0]=['core','conditions','rules','libs','tools']
import query_base as qb
s1=qb.RunSpec(seeds=[], cond_name='煎煮')
s2=qb.RunSpec(seeds=[], cond_name='煎煮', reagents=('NaBH4','Cs2CO3'))
print('no reagents ->', s1.cond().reagents)
print('with reagents ->', s2.cond().reagents)
print('template untouched ->', s1.cond().solvent, s1.cond().temperature)
