import pymupdf,glob,sys
p=glob.glob('books/*Art in detail*')[0]
d=pymupdf.open(p)
for i,pg in enumerate(d):
    z=2200/pg.rect.width
    pg.get_pixmap(matrix=pymupdf.Matrix(z,z)).save(f'.scratch/clean_hodge/img/p{i+1:04d}.png')
print(len(d), d[0].rect)
