import os 
import json 
from apscheduler .schedulers .background import BackgroundScheduler 
from flask import Flask 
from db import init_db ,db 
from models import User ,AgentResult 
from .import aggregation_agent ,visual_prep_agent ,narration_agent 
def create_app ():
    app =Flask (__name__ )
    init_db (app )
    return app 
def run_all_agents_once ():
    app =create_app ()
    results ={'users':0 }
    with app .app_context ():
        users =User .query .all ()
        for u in users :
            try :
                agg =aggregation_agent .aggregate_user_data (u .id ,months =12 )
                vp =visual_prep_agent .prepare_and_store (agg ,u .id ,db ,AgentResult )
                narration =narration_agent .generate_narration (agg ,user_id =u .id )
                try :
                    ar =AgentResult (agent_key ='narration_agent_v1',user_id =u .id ,payload =json .dumps (narration ))
                    db .session .add (ar )
                    db .session .commit ()
                except Exception :
                    db .session .rollback ()
                results ['users']+=1 
            except Exception as e :
                print ('Error running agents for user',u .id ,e )
    return results 
_scheduler =None 
def start (period_minutes :int =15 ):
    global _scheduler 
    if _scheduler is not None :
        return _scheduler 
    _scheduler =BackgroundScheduler ()
    _scheduler .add_job (run_all_agents_once ,'interval',minutes =period_minutes ,id ='run_agents')
    _scheduler .start ()
    print (f'Agent scheduler started (every {period_minutes} minutes)')
    return _scheduler 
def shutdown ():
    global _scheduler 
    if _scheduler :
        _scheduler .shutdown (wait =False )
        _scheduler =None 
if __name__ =='__main__':
    print ('Running agents once...')
    r =run_all_agents_once ()
    print ('Done. Results:',r )
