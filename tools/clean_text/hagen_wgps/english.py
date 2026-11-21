import re
D=set(x.strip().lower() for x in open('/usr/share/dict/words'))
def _base(w):
    c=[w]
    for a,b in (('ies','y'),('ied','y'),('ing',''),('ing','e'),('ed',''),('ed','e'),('es',''),('s',''),('ly',''),('ier','y'),('iest','y'),('er',''),('er','e'),('est',''),('est','e'),('ness',''),('ment',''),('ments',''),('ful',''),('less',''),('able','e'),('able',''),('ish',''),('ally',''),('ically','ic'),('ity',''),('ities','ity'),('d','')):
        if w.endswith(a) and len(w)-len(a)>=3: c.append(w[:-len(a)]+b)
    # doubled consonant
    for x in list(c):
        if len(x)>3 and x[-1]==x[-2]: c.append(x[:-1])
    return c
def brit(w):
    v=[w]
    for a,b in (('our','or'),('ours','ors'),('oured','ored'),('ouring','oring'),('ourable','orable'),('ise','ize'),('ised','ized'),('ising','izing'),('isation','ization'),('isations','izations'),('ises','izes'),('re','er'),('res','ers'),('red','er'),('lled','led'),('lling','ling'),('ller','ler'),('ogue','og'),('ence','ense'),('ae','e'),('oe','e'),('ll','l'),('mme','m'),('ement','ment'),('ourite','orite'),('ourites','orites'),('ouring','oring'),('ourful','orful'),('oured','ored'),('ourless','orless'),('ought','ought')):
        if w.endswith(a): v.append(w[:-len(a)]+b)
        if a in w and a in ('ae','oe','our'): v.append(w.replace(a,b))
    return v
def valid_en(w):
    w=w.lower()
    for x in brit(w):
        for y in _base(x):
            if y in D: return True
            for z in brit(y):
                if z in D: return True
    return False
