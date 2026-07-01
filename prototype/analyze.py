from prototype.game import init_game, step_game
from prototype.eval import load_ai
import random
ai0=load_ai("greedy")
ai1=load_ai("greedy")
mc=[0,0]
td=[[],[]]
cl=[0,0]
for s in range(42,142):
 gs=init_game(seed=s,size=15,generator_id="balanced")
 r0=random.Random(s);r1=random.Random(s+1)
 while gs.winner is None and gs.turn<100:
  step_game(gs,ai0(gs,0,r0),ai1(gs,1,r1))
 for p in[0,1]:
  cc=gs.techs[p].construction_count()
  if cc>mc[p]:mc[p]=cc
  td[p].append(len(gs.techs[p].completed))
  for t in["C1","C2","C3","C4","C5"]:
   if t in gs.techs[p].completed:cl[p]+=1
print(f"Max construction: P0={mc[0]}/5 P1={mc[1]}/5")
print(f"Avg techs: P0={sum(td[0])/100:.1f} P1={sum(td[1])/100:.1f}")
print(f"C-line completions: P0={cl[0]} P1={cl[1]}")
