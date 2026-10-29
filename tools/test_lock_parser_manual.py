from techlog import parse_lock_event

sample = (
    "03:28.039032-3,TLOCK,2,level=INFO,"
    "process=1cv8c,OSThread=20716,Usr=DefUser,"
    "DBMS=DBV8DBEng,DataBase=ERP,"
    "Regions=Reference69.REFLOCK,"
    "Locks='Reference69.REFLOCK Shared "
    "Fld2295=0 ID=69:b0a17c10c924aec011f1d1eaa847bbb1',"
    "Context='Пример контекста'"
)

result = parse_lock_event(sample)

print(result)
