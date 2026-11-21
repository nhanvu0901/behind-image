"""Proper-name corrections for grovier_nws (machine-translated print). Run after grovier.py.
Each rule: (regex, replacement, page range or None, reason). Only names whose right form is certain from the book's
own contents page (TOC) / captions / index, or from the unmistakable artist or work under discussion."""
import re,glob,json,collections
ROOT='/Users/nhanvu/Documents/code/behind-the-image'
D=f'{ROOT}/library/clean_text/grovier_nws'
TOC='contents (TOC) names the artist/work'
IDN='unmistakable artist/work under discussion in this chapter'
def R(pats,to,pages=None,why=TOC):
    return [(r'\b(?:'+'|'.join(pats)+r')\b',to,pages,why)]
rules=[]
# --- pair rules first (first names + surnames)
rules+=[(r'\bEdward Manai\b','Édouard Manet',None,TOC+' (37: Édouard Manet)'),
 (r'\bEduard Mane\b','Édouard Manet',None,TOC+' (37: Édouard Manet); caption of his Execution of Maximilian'),
 (r'\bGeorge Shura\b','Georges Seurat',None,TOC+' (38: Georges Seurat)'),
 (r'\bHenry Mattis\b','Henri Matisse',None,TOC+' (43: Henri Matisse)'),
 (r'\b(?:Louis|Luis) (?:Buerjoa|Buerchoa|Bolchoa|Buljoa|Bulchoa|Boljoa|Burchoa|Burjoa|Bouroucho)\b','Louise Bourgeois',None,TOC+' (56: Louise Bourgeois, Maman); caption "Spider"'),
 (r'\bRoger van de[r]? (?:Wedden|Wheden)\b','Rogier van der Weyden',None,TOC+' (13: Rogier van der Weyden)'),
 (r'\bVan (?:Guang|Kuan)\b','Fan Kuan',None,TOC+' (8: Fan Kuan)'),
 (r'\bYeronimes Bos\b|\bJeronimes Bos\b','Hieronymus Bosch',None,TOC+' (18: Hieronymus Bosch)'),
 (r'\bMatias (?=Gr[uü])','Matthias ',None,TOC+' (21: Matthias Grünewald)'),
 (r'\bPiero de la Francesca\b','Piero della Francesca',None,'unmistakable: Piero della Francesca (San Antonio polyptych)'),
 (r'\bZian (?:Laurento|Lorenzo) ','Gian Lorenzo ',None,TOC+' (26: Gian Lorenzo Bernini)'),
 (r'\bMichelangelo Melisi de ','Michelangelo Merisi da ',None,'index/credits spell Merisi; unmistakable Caravaggio'),
 (r'\bJogio Vassari\b','Giorgio Vasari',None,'the book itself prints "Giorgio Vasari" (p170); Vasari biographer of the Renaissance'),
 (r'\bSandro Poticelli\b','Sandro Botticelli',None,TOC+' (16)'),
]
rules+=R(['Dushan','Dusan','Dushanbe'],'Duchamp',(303,308),TOC+' (45: Marcel Duchamp, Fountain)')
rules+=R(['Dushan'],'Duchamp',(120,135),TOC+' (Marcel Duchamp, L.H.O.O.Q.)')
rules+=R(['Dushan'],'Duchamp',(355,360),TOC+' (Marcel Duchamp)')
rules+=R(['Avclint','Afclint','Avkrint','Foklint','Avclinter','Afcrinter'],'af Klint',(278,283),TOC+' (41: Hilma af Klint)')
rules+=R(['Benini','Benitini'],'Bernini',None,TOC+' (26: Gian Lorenzo Bernini)')
rules+=R(['Massacho','Masacho'],'Masaccio',None,TOC+' (11: Masaccio)')
rules+=R(['Shura'],'Seurat',None,TOC+' (38: Georges Seurat)')
rules+=R(['Aniel'],'Asnières',(261,265),TOC+' (38: Bathers at Asnières)')
rules+=R(['Brilow'],'Brillo',None,TOC+' (53: Brillo Boxes)')
rules+=R(['Vohor'],'Warhol',(355,360),TOC+' (53: Andy Warhol)')
rules+=R(['Bax'],'Bacchus',None,TOC+' (22: Bacchus and Ariadne)')
rules+=R(['Manai','Mannet'],'Manet',None,TOC+' (37: Édouard Manet)')
rules+=R(['Wimir','Vimir'],'Vermeer',None,TOC+' (28: Johannes Vermeer)')
rules+=R(['Tura','Toula','Tula'],'Trajan',(47,55),TOC+' (6: Trajan\'s Column)')
rules+=R(['Mantanya','Manteña','Mantenia'],'Mantegna',None,TOC+' (15: Andrea Mantegna)')
rules+=R(['Poticelli','Potticelli','Potichelli'],'Botticelli',None,TOC+' (16: Sandro Botticelli)')
rules+=R(['Wedden','Wheden'],'Weyden',None,TOC+' (13: Rogier van der Weyden)')
rules+=R(['Rogel'],'Rogier',(94,99),TOC+' (13: Rogier van der Weyden)')
rules+=R(['Mattis','Martís'],'Matisse',None,TOC+' (43: Henri Matisse)')
rules+=R(['Monay','Monai','Monnet'],'Monet',None,TOC+' (44: Claude Monet)')
rules+=R(['Caravacho','Karavacho','Calavacho','Caravajo','Karavajo'],'Caravaggio',None,TOC+' (25: Caravaggio)')
rules+=R(['Melisi'],'Merisi',(176,183),'index/credits spell Merisi; Caravaggio (25)')
rules+=R(['Connell'],'Cornell',(327,333),TOC+' (49: Joseph Cornell)')
rules+=R(['Constair','Constabel','Constabal','Constebel','Constairs'],'Constable',None,TOC+' (33: John Constable)')
rules+=R(['Daly','Dalli','Dallie','Darley'],'Dalí',None,TOC+' (47: Salvador Dalí)')
rules+=R(['Darryn','Darry','Darrye'],'Dalí',(316,320),TOC+' (47: Salvador Dalí)')
rules+=R(['Joto','Jotto'],'Giotto',None,IDN+' (Giotto; index "Joto di Bondona" = Giotto di Bondone)')
rules+=R(['Kyles','Kels'],'Kells',None,TOC+' (7: The Book of Kells)')
rules+=R(['Eisenheim'],'Isenheim',None,TOC+' (21: The Isenheim Altarpiece)')  # 'Issenheim' is a correct spelling (the village); left as printed
rules+=R(['Grenica','Gernica','Grenika'],'Guernica',None,TOC+' (48: Guernica)')
rules+=R(['Kostanza'],'Costanza',None,IDN+' (Costanza Bonarelli, Bernini\'s model)')
rules+=R(['Lein'],'Rijn',(180,180),TOC+' (29: Rembrandt van Rijn)')
rules+=R(['Brugell','Bruguel','Burugall'],'Bruegel',None,IDN+' (Pieter Bruegel the Elder)')
rules+=R(['Boljoa','Buerjoa','Buljoa','Bulchoa','Bouroucho','Buerchoa','Bolchoa','Burchoa','Burjoa'],'Bourgeois',None,TOC+' (56: Louise Bourgeois)')
rules+=R(['Abramovich'],'Abramović',None,TOC+' (57: Marina Abramović)')  # 'Abramovic' (no diacritic) is a spelling variant, left
rules+=R(['Tintolito','Dintoreto','Dintoreito','Dintore','Tintoreto','Dittoreito'],'Tintoretto',None,TOC+' (24: Tintoretto)')
rules+=R(['Heraclit','Heraklit'],'Heraclitus',(145,149),IDN+' (Heraclitus in Raphael\'s School of Athens, TOC 20)')
rules+=R(['Gwensen'],'Godwinson',(67,74),IDN+' (Harold Godwinson, Bayeux Tapestry, TOC 9)')
rules+=R(['Fusely','Fuselli','Füsselly'],'Fuseli',None,TOC+' (31: Henry Fuseli)')
rules+=R(['Raocon','Raocón','Raacón','Raakon','Laocon','Laocone'],'Laocoön',None,TOC+' (5: Laocoön and His Sons)')
rules+=R(['Cézane','Cézan','Cessanne','Cézant'],'Cézanne',None,TOC+' (40: Paul Cézanne)')
rules+=R(['César'],'Cézanne',(273,277),IDN+' (Cézanne, Large Bathers, TOC 40)')
rules+=R(['Chulasquez','Chulaskez','Hulasquez','Erasquez','Chalascez','Chulas'],'Velázquez',None,TOC+' (27: Diego Velázquez)')
rules+=R(['Renbrandt','Rembrand','Lembrandt'],'Rembrandt',None,TOC+' (29: Rembrandt)')
rules+=R(['Sculley','Sculli','Scuri','Sculi'],'Scully',(360,365),TOC+' (54: Sean Scully)')
rules+=R(['Sculli'],'Scully',(396,396),TOC+' (54: Sean Scully)')
rules+=R(['Vassari','Wasary'],'Vasari',None,'the book itself prints "Vasari" (p123, p170); biographer of the Renaissance')
rules+=R(['Tician','Titsian','Titsy','Tissian','Tissing','Tisana','Titsa','Tisham','Titham'],'Titian',None,TOC+' (22: Titian)')
rules+=R(['Tishan'],'Titian',(276,276),IDN+' ("Titian and Rubens")')
rules+=R(['Hemesen'],'Hemessen',(412,412),TOC+' (23: Catharina van Hemessen)')
rules+=R(['Bingan','Binggen'],'Bingen',None,TOC+' (10: Hildegard of Bingen)')
rules+=R(['Grunevald','Grunnelwald','Grunnewald','Graunewald'],'Grünewald',None,TOC+' (21: Matthias Grünewald)')
rules+=R(['Kerim'],'Klimt',(284,284),IDN+' (Klimt, TOC 42)')
rules+=R(['Innosen','Innoxin'],'Innocent',(347,354),TOC+' (52: Pope Innocent X)')
rules+=R(['Mom'],'Mom',(0,0),'')  # placeholder: title "Maman" left as printed (translation, not a mangled name)
rules=[r for r in rules if r[3]]

# --- second pass (verifier R6): certain misses, same exception rule
rules[0:0]=[
 (r'\bJan [Vv]an Ike\b','Jan van Eyck',None,TOC+' (12: Jan van Eyck); entry title prints Eyck'),
 (r"\bVan Ike(?=['’]s|,| )",'Van Eyck',None,TOC+' (12: Jan van Eyck)'),
 (r'\bRoger [Vv]an [Dd]e Weyden\b','Rogier van der Weyden',None,TOC+' (13: Rogier van der Weyden)'),
 (r'\bVla (?=Ang[a-z]*)','Fra ',None,TOC+' (14: Fra Angelico)'),
 (r'\bCatherine Van van Hemessen\b','Catharina van Hemessen',None,TOC+' (23: Catharina van Hemessen); heading prints it'),
 (r'\bFilippo Brunelsky\b','Filippo Brunelleschi',None,'next sentence prints Brunelleski; unmistakable Brunelleschi (perspective, 1413)'),
 (r'\bNew Grandchage\b','Newgrange',(56,60),IDN+' (Newgrange, Book of Kells chapter)'),
 (r'\bDuke of Dubelli\b','Duke of Berry',(94,99),IDN+' (Limburg brothers, Tres Riches Heures)'),
 (r'\bLas Caziz\b','Velázquez',(347,354),IDN+' (Portrait of Pope Innocent X is by Velázquez)'),
]
rules+=R(['Angiliko','Angilico','Anglico'],'Angelico',None,TOC+' (14: Fra Angelico)')
rules+=R(['Brunelsky','Brunelleski','Bruneleski','Brunell'],'Brunelleschi',None,'unmistakable: Brunelleschi (Florentine perspective)')
rules+=R(['Wenklman','Wenkelman'],'Winckelmann',None,'the book prints "Winckelmann" on p45 (Laocoön chapter)')
rules+=R(['Lacein'],'Lessing',(46,46),'the book names Lessing on p45 (Laocoön chapter)')
rules+=R(['Dushing'],'Duchenne',(46,46),'same paragraph names Duchenne (facial expressions)')
rules+=R(['Lipanda'],'Ripanda',(47,47),'p47 prints "Ripanda" for the same Trajan\'s Column figure')
rules+=R(['Apolloros','Apolodoros','Apollodoros'],'Apollodorus',None,TOC+' (6: Apollodorus of Damascus)')
rules+=R(['Dacias'],'Dacians',(47,55),IDN+' (Trajan\'s Dacian wars)')
rules+=R(['Louven'],'Leuven',(95,95),IDN+' (Descent from the Cross, Leuven)')
rules+=R(['Skorovini'],'Scrovegni',(107,107),'index/credits print "Scrovegni" (p399); Padua chapel')
rules+=R(['Wozworth','Wazworth'],'Wordsworth',(24,27),IDN+' (Keats and Wordsworth on the Elgin Marbles)')
rules+=R(['Büngen','Minchgen'],'Bingen',(75,79),TOC+' (10: Hildegard of Bingen)')
rules+=R(['Blancachi'],'Brancacci',(80,88),'credits print "Brancacci Chapel" (p398); Masaccio fresco')
rules+=R(['Dionyssos'],'Dionysus',(36,40),IDN+' (Villa of the Mysteries)')
rules+=R(['Polubius'],'Polybius',(52,52),IDN+' (Polybius, ancient historian)')
rules+=R(['Carnix','Cannicus','Cannix','Canyx'],'Carnyx',(52,52),IDN+' (Celtic war trumpet in Trajan\'s Column)')
rules+=R(['Misshire'],'Meath',(59,59),IDN+' (Newgrange, Co. Meath)')
rules+=R(['Fratford'],'Stratford',(232,235),IDN+' (Constable, Stratford Mill)')
rules+=R(['Pruto'],'Pluto',(312,313),IDN+' (American Gothic chapter, myth of Persephone)')
rules+=R(['Mento'],'Mentor',(24,26),IDN+' (the ship Mentor carrying the Parthenon marbles)')
rules+=R(['Kathlina'],'Catharina',(163,169),TOC+' (23: Catharina van Hemessen)')
rules+=R(['Anofenis'],'Arnolfini',(198,198),IDN+' (Arnolfini Portrait, 1434, 82.2 x 60 cm)')
rules=[r for r in rules if r[3]]
def apply():
    log=collections.defaultdict(list); total=collections.Counter()
    for f in sorted(glob.glob(f'{D}/page_*.txt')):
        n=int(f[-8:-4]); s=open(f,encoding='utf-8').read(); orig=s
        for pat,to,pg,why in rules:
            if pg and not (pg[0]<=n<=pg[1]): continue
            def sub(m):
                total[(m.group(0),to)]+=1
                log[n].append({'from':m.group(0),'to':to,'reason':why})
                return to if not to.endswith(' ') else to
            s=re.sub(pat,sub,s)
        if s!=orig: open(f,'w',encoding='utf-8').write(s)
    return log,total
if __name__=='__main__':
    log,total=apply()
    json.dump({str(k):v for k,v in log.items()},open(f'{ROOT}/.scratch/clean_digital/grovier_corrections.json','w'),ensure_ascii=False)
    print('pages changed',len(log),'replacements',sum(total.values()),'distinct pairs',len(total))
