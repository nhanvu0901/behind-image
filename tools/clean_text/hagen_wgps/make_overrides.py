"""Reader-pass overrides: every entry here was made by reading the page image."""
import json,os
O={}
def add(n,**kw): O['%04d'%n]=dict(O.get('%04d'%n,{}),**kw)
def rep(n,a,b,reason='read page image'):
    add(n,read=True,replace=O.get('%04d'%n,{}).get('replace',[])+[dict({'from':a,'to':b,'reason':reason})])
# --- front/back matter
add(1,full=[['h1','What Great Paintings Say'],['para','Volume 1'],['para','Rose-Marie & Rainer Hagen'],['para','TASCHEN']],type='front',read=True)
add(5,full=[['h1','What Great Paintings Say'],['para','Volume 1']],type='front',read=True)
add(6,type='plate',full=[],read=True)
add(7,full=[['h1','What Great Paintings Say'],['para','Volume 1'],['para','Rose-Marie and Rainer Hagen'],['para','TASCHEN'],['para','KÖLN LONDON LOS ANGELES MADRID PARIS TOKYO']],type='front',read=True)
add(8,type='credits',read=True,full=[
 ['credit','Cover: Diego Velázquez, Venus at her Mirror, c. 1646, Oil on canvas, 123 x 177 cm, London, National Gallery, Photo: AKG Berlin'],
 ['credit','Backcover: Georges de La Tour, The Fortune Teller, after 1630, Oil on canvas, 102 x 123 cm, New York, The Metropolitan Museum of Art, Photo: AKG Berlin / Erich Lessing'],
 ['credit','Illustration Page 2: Peter Paul Rubens, The Love Garden (detail), c. 1632-1634, Oil on canvas, 198 x 283 cm, Derechos reservados © Museo del Prado, Madrid'],
 ['para','To stay informed about upcoming TASCHEN titles, please request our magazine at www.taschen.com or write to TASCHEN America, 6671 Sunset Boulevard, Suite 1508, USA-Los Angeles, CA 90028, Fax: +1-323-463 4442. We will be happy to send you a free copy of our magazine which is filled with information about all of our books.'],
 ['para','© 2003 TASCHEN GmbH, Hohenzollernring 53, D-50672 Köln, www.taschen.com'],
 ['para','Original edition © 2000 Benedikt Taschen Verlag GmbH'],
 ['para','© 2002 for the illustrations of Marc Chagall, James Ensor and Otto Dix: VG Bild-Kunst, Bonn'],
 ['para','Editing and layout: Simone Philippi, Susanne Uppenbrock, Cologne'],
 ['para','English Translation: Iain Galbraith, Wiesbaden; Karen Williams, Whitley Chapel'],
 ['para','Cover design: Claudia Frey, Angelika Taschen, Cologne'],
 ['para','Printed in Slovenia'],['para','ISBN 3-8228-2100-4']])
add(499,type='back',read=True,full=[
 ['h1','Masterpieces under the microscope'],
 ['para','From ancient Egyptian papyrus scrolls to 20th century works: painting’s hidden secrets revealed'],
 ['para','New! What Great Paintings Say Volume 2, Rose-Marie & Rainer Hagen'],
 ['quote','“This book unravels the symbolism located in plain view in many Old Masters that remains overlooked by many of today’s observers.” —Adventures, United States'],
 ['quote','“Amazingly informative and readable ... An important addition to art history literature.” —The Sanford Herald, United States'],
 ['para','What Great Paintings Say Vol. 2, Rose-Marie & Rainer Hagen. English, German, French and Spanish editions. Flexi-cover, format: 19.6 x 24.5 cm (7.7 x 9.6 in.), 432 pp. US$ 39.99 / £ 19.99 / € 29.99 / ¥ 4,500'],
 ['para','www.taschen.com']],issues=['advertisement page; the printed word "reamins" in the first review quote is a misprint, corrected to "remains" only here because Vision and the page agree on the other letters (read from image)'])
add(504,type='back',read=True,full=[
 ['para','What is that callow youth doing among the gypsies? What was the penalty for stealing a gold coin or a purse? Is the painting an ingenious fake? How did it make its way from France to the United States?'],
 ['para','These are the kinds of question Rose-Marie and Rainer Hagen ask when faced with world-famous masterpieces. In the language of today they comment on the fashions and attitudes, trends and intrigues, love, vice and lifestyles of past times.'],
 ['para','ISBN 3-8228-2100-4']])
# --- openers: headline / artist lines
rep(24,'Due de Berry','Duc de Berry')
rep(157,'Caliarl','Caliari')
rep(186,'Tiburtine Sybil,','Tiburtine Sybil, c. 1580')
add(198,read=True,delete_match=[dict(kind='h2',text='El Greco: The Burial of Count Orgaz, 1586')],insert=[dict(index=1,kind='meta',text='El Greco: The Burial of Count Orgaz, 1586')])
rep(205,'Armada Portrait of Elizabeth','Armada Portrait of Elizabeth I, c. 1590')
O['0205']['delete_match']=[dict(kind='h2',text='I, c. 1590')]
rep(276,'Charles Le Brum The Chancellor Seguier','Charles Le Brun: The Chancellor Séguier')
rep(379,'Theodore Géricault','Théodore Géricault')
rep(384,'Eugene Delacroix','Eugène Delacroix')
rep(444,'The Luncheon of the Boating Party, 1881','Pierre Auguste Renoir: The Luncheon of the Boating Party, 1881')
rep(451,'Folies Bergere','Folies Bergère')
add(360,read=True,issues=['no artist/title line is printed on this opening page (checked on the image); works.json gives Jacques-Louis David: The Coronation of Napoleon, 1807'])
# --- junk headings
add(77,read=True,delete_match=[dict(kind='h2',text='if')])
add(131,read=True,delete_match=[dict(kind='h2',text='in.1-')])
# --- lost drop caps / first words
rep(272,'eventeenth century spectators','Seventeenth century spectators','drop cap S lost in text layer')
rep(416,'think there were two hundred','I think there were two hundred','drop cap I lost in text layer')
rep(417,'was customary neither in Lady Montagu','It was customary neither in Lady Montagu','drop cap I lost in text layer')
rep(478,'nees together, feet apart','Knees together, feet apart','drop cap K lost in text layer')
rep(478,'uch had changed since the war','Much had changed since the war','drop cap M lost in text layer')
rep(470,'% # ive la Sociale” are the words writ-\\g ten ab°ve the heads of the crowd: w the banner reads','“Vive la Sociale” are the words written above the heads of the crowd: the banner reads','drop cap V and OCR specks')
# --- specks / digits
rep(12,"is'told","is told"); rep(113,'~is wrapped','is wrapped'); rep(129,'*of France','of France'); rep(141,'whilę^ their','while their')
rep(153,"was'sure","was sure"); rep(168,'\\ enice possessed','Venice possessed'); rep(168,'V hatever','Whatever'); rep(168,'Doge s palace','Doge’s palace')
rep(168,'In 184S','In 1848','digit misread'); rep(198,'>f the painting','of the painting'); rep(218,'°no doubt','no doubt'); rep(218,'in 160C;','in 1600;','digit misread')
rep(224,'^With the help','with the help'); rep(231,'foretell.”*','foretell.”'); rep(257,'rulers,^artists','rulers, artists'); rep(382,"on'the distant","on the distant")
rep(409,"the'people","the people"); rep(421,'German* Reich','German Reich'); rep(455,'^perspective','perspective'); rep(455,"the'reflection","the reflection"); rep(478,"With'her","With her")
rep(312,'“A1 fresco”','“Al fresco”'); rep(138,'“1’homme','“l’homme'); rep(273,'favour... ”2','favour...”'); rep(429,'1-858','1858')

rep(279,'chancellor^ department','chancellor’s department'); rep(397,'is<a lavish','is a lavish'); rep(416,'who* after','who, after'); rep(495,'Fran^ais','Français')
rep(497,"thyroi'de","thyroïde")
for a,b in (('452^157','452-457'),('464^169','464-469'),('44^19','44-49'),('422^127','422-427')): rep(498,a,b,'dash misread as ^')
add(26,read=True,replace_head=dict(count=2,items=[
 ['para','in the Middle Ages, especially those by the Limburg Brothers, Herman, Jean and Paul. Born in Nijmegen, they worked for the Duc de Berry from about 1405. By 1416, all three were dead, presumably the victims of an epidemic.'],
 ['h2','A hard life on the land'],
 ['para','It is difficult to make out the donkey’s load, but it is probably wood. Only branches and brushwood were burned by the villagers for cooking and heating. Tree-trunks were reserved for the duke’s own hearth, or were used to build houses.']],
 reason='first paragraph garbled in the text layer beside the picture; rewritten from the page image'))
add(486,read=True,full=[
 ['h1','400 years at a glance'],
 ['meta','Diego Rivera: Dream of a Sunday Afternoon in Alameda Park, 1948'],
 ['para','If you want to take a proper look at the whole of Diego Rivera’s 4.8-metre-high mural, you’ll need to take a walk – along all 15 metres of its length, and past almost 150 different characters. By European standards, the format is enormous – as enormous, indeed, as the task which the artist set himself: to bring together figures from the past 400 years into a panorama of the history of his country, set in Alameda Park.'],
 ['para','The park lies in Mexico City, and on Sunday afternoons the capital’s inhabitants still gather here to sit, stroll, chat and picnic. The grown-ups buy balloons and windmills for their children, and the adolescents wade in the fountain which Rivera has portrayed in the centre of his composition. He has placed well-known figures from Mexican history alongside many more who are unknown, and has also incorporated mythical figures such as angels and Death, as well as members of his own family. This is no official historical record, in other words, no Social Realism, but a collage just as might be experienced in a dream.'],
 ['para','The chronology of the mural nevertheless unfolds more or less logically from left to right. At the apex of three small pyramids of figures distributed across the composition, Rivera portrays three Mexican presidents: on the left, Benito Juárez, head of state from 1858 to 1872, is holding the written constitution in his hands. Just to the right of centre is the uniformed, sleeping figure of Porfirio Díaz, who held office for over 30 years before being ousted by Francisco Madero. The latter can be seen, raising his hat in greeting, near the right-hand edge of the mural; in 1913 he was assassinated.'],
 ['para','Beneath them, along the lower edge of the mural, are those who have no hand in politics, but who suffer its effects: ordinary citizens, Indians, agricultural workers, and the poor. The conflict between these people and those in power was one which Rivera painted many times. On the left, a thin youth is picking the pocket of a well-dressed gentleman; in the middle, an Indian woman in a yellow dress strikes an']],
 issues=['whole page rewritten from the page image: the text layer interleaved two columns of the introduction'])
json.dump(O,open(os.path.dirname(os.path.abspath(__file__))+'/overrides.json','w'),ensure_ascii=False,indent=1)
print(len(O))
