import pymupdf,glob
p=glob.glob('/Users/nhanvu/Documents/code/behind-the-image/books/*Art in detail*')[0]
d=pymupdf.open(p)
for i,pg in enumerate(d):
    z=3000/pg.rect.width
    pg.get_pixmap(matrix=pymupdf.Matrix(z,z),colorspace=pymupdf.csGRAY).save(f'/Users/nhanvu/Documents/code/behind-the-image/.scratch/clean_hodge/img3/p{i+1:04d}.png')
