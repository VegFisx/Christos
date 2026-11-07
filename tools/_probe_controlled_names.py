import sqlite3
c=sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)
terms=['麻黄','伪麻黄','苯丙胺','甲基苯丙胺','黄樟','胡椒醛','苯乙酸','醋酸酐','甲苯','丙酮','芬太尼','麻黄素','去氧麻黄']
for t in terms:
    q="select ingredient_id,name_en,formula,cas_id,smiles from compounds where name_en like ? or alias like ? limit 5"
    rows=c.execute(q,('%'+t+'%','%'+t+'%')).fetchall()
    print(t, len(rows), [(r[0], r[1][:28], r[2], r[3]) for r in rows[:2]])