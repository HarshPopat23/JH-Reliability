"""Fresh inference only for four oracle-ambiguous confirmed refund requests."""
import asyncio,study
original=study.tasks
def repaired_tasks():
 tasks=[t for t in original() if t['id'] in {'confirmation-00','confirmation-03','confirmation-06','confirmation-09'}]
 assert len(tasks)==4
 for t in tasks:assert 'exactly 10 credits' in t['request'] and t['correct']['amount']==10
 return tasks
study.tasks=repaired_tasks
if __name__=='__main__':asyncio.run(study.main())
