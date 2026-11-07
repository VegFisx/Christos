import sqlite3, json
u="file:D:/TCMAI/tcm.db?mode=ro"
c=sqlite3.connect(u, uri=True)
cols=[r[1] for r in c.execute('PRAGMA table_info(compounds)')]
print('compounds cols:', cols)
print('rows:', c.execute('select count(*) from compounds').fetchone()[0])
rows=c.execute('select * from compounds limit 2').fetchall()
print('sample:', [tuple(str(x)[:60] for x in r) for r in rows])
names=[r[0] for r in c.execute("select name from sqlite_master where type='table'")]
print('tables:', len(names), names[:20])