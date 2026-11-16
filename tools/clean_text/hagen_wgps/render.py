import pymupdf,sys,glob
pdf=glob.glob('/Users/nhanvu/Documents/code/behind-the-image/books/*What Great Paintings Say*')[0]
d=pymupdf.open(pdf)
out='/Users/nhanvu/Documents/code/behind-the-image/.scratch/clean_hagen/img/'
for i,p in enumerate(d):
    z=1600/p.rect.width
    p.get_pixmap(matrix=pymupdf.Matrix(z,z)).save(out+'p%04d.png'%(i+1))
print(len(d), d[11].rect)
