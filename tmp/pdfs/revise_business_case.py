from pathlib import Path
import re

p=Path(__file__).with_name('build_document.py')
s=p.read_text(encoding='utf-8-sig')

def replace(old,new):
    global s
    if old not in s: raise ValueError('Missing replacement: '+old[:100])
    s=s.replace(old,new)

replace("OUT=ROOT/'output/pdf/Dokumentazioa - D Taldea - Segurtasuna eta lege-betetzea.pdf'", "OUT=ROOT/'output/pdf/Dokumentazioa - Jefrys - Segurtasuna eta lege-betetzea.pdf'")
replace('Dokumentazio honetan deskribatutako prototipoak simulagailuko telemetria eta ai4i2020_train.csv fitxategia erabiltzen ditu. Horrek ez du frogatzen ARAKAIN Makineriak enpresak benetako produkzio-datuak eman dituenik. Datu errealetarako sarbidea ez da baimendutzat joko sinatutako akordiorik gabe.',
        'ARAKAIN Makineriak enpresak Jefrys kontratatu du CNC Guard garatu eta ezartzeko. Proiektuko telemetria ARAKAINen CNC makinen produkzio-datuak dira. ai4i2020_train.csv fitxategiak enpresak emandako datu historikoak biltzen ditu, eta etengabeko CSV fluxuak makinen uneko neurketak jasotzen ditu.')
replace('## 6.1.1 Simulaziorako aukeratutako harremana','## 6.1.1 ARAKAIN eta Jefrys enpresen arteko harremana')
replace('Ariketa honetan, ARAKAIN Makineriak telemetria ez-pertsonala erabiltzeko baimen mugatua ematen diola D Taldeari simulatzen da.',
        'ARAKAIN Makineriak Jefrysi bere telemetria eskuratzeko eta erabiltzeko baimen mugatua ematen dio, kontratatutako garapena, entrenamendua, balidazioa eta ezarpena egiteko.')
replace('Softwareari dagokionez, doako erabilera-lizentzia ez-esklusiboa aukeratzen da, iturburu-kodea entregatuta.',
        'Softwareari dagokionez, ordainpeko erabilera-lizentzia ez-esklusiboa ematen da, iturburu-kodea entregatuta. Garapenaren, ezarpenaren eta lizentziaren prezio osoa 6.000 euro da, BEZa aparte, ordainketa bakarrean.')
replace('## 6.1.2 Hiru datu-mota bereiztea','## 6.1.2 Enpresak emandako datuak')
replace('| Simulagailuko datuak eta UCI AI4I 2020 | Jatorria eta lizentzia dokumentatu; CC BY 4.0 atribuzioa mantendu. |',
        '| ARAKAINen datu historikoak | Entrenamendurako eta balidaziorako erabilera mugatua; ez dira Jefrysen jabetza bihurtzen. |')
replace('Kontratu-ereduak simulazio akademikorako prestatu dira. Sinadura, IFZ, helbide eta ordezkaritza eremuak bete gabe daude; ez dute benetako baimenik edo sinatutako kontraturik ordezten.',
        'Kontratu-eranskinetan bezeroa ARAKAIN Makineriak da, eta hornitzailea Jefrys. IFZ, helbide, ordezkari eta sinadura eremuak formalizazioan beteko dira. Datuak eskuratzeko baimena zerbitzu-kontratuari lotuta dago; ez da datuen titulartasunaren lagapena.')
replace('Taldeak hornitzailearen rola eta enpresak hedatzailearen rola izan ditzakete benetako merkaturatze edo zerbitzuan jartze batean. Prototipo akademikoa izateak ez du produkzio-erabilera automatikoki salbuesten. Merkaturatu aurretik rolak, salbuespenen aplikagarritasuna eta sailkapena dokumentatuko dira.',
        'Jefrys CNC Guard-en hornitzailea da, eta ARAKAIN Makineriak sistema erabiltzen duen enpresa hedatzailea. Jefrysek aurreikusitako helburua, bertsioa eta erabilera-jarraibideak dokumentatuko ditu; ARAKAINek baimendutako erabilera eta giza gainbegiraketa bermatuko ditu. Produkzioan jarri aurretik sailkapena eta aplikagarri diren betebeharrak berrikusiko dira.')
replace('## 6.6.1 Simulaziorako kontserbazio-politika','## 6.6.1 Zerbitzuaren kontserbazio-politika')
replace('| Enpresaren CSVak eta taldearen lan-kopiak | Pilotuak irauten duen bitartean, gehienez 90 egun; amaitzean itzuli eta 30 egunetan ezabatu. |',
        '| Enpresaren CSVak eta Jefrysen lan-kopiak | Hasierako ezarpen-zerbitzuan, gehienez 90 egun; amaitzean itzuli eta 30 egunetan ezabatu. |')
replace('simulazioko barne-konpromisoa','kontratuko jakinarazpen-epea')
replace('Simulazioan ez da softwarearen jabetza osoa saltzen. D Taldeak bere ekarpenen ustiapen-eskubideak mantentzen ditu, eta ARAKAIN Makineriak doako lizentzia ez-esklusiboa jasotzen du, epe mugagabean eta mundu osoan, bere barne-erabilerarako. Lizentzia erabiltzeko baimena da; ez da egiletzaren edo eskubide guztien eskualdaketa.',
        'Jefrysek CNC Guard garatu eta ezartzeko zerbitzua eta ordainpeko lizentzia eskaintzen dizkio ARAKAIN Makineriak enpresari. Prezio osoa 6.000 euro da, BEZa aparte: 4.500 euro garapen eta ezarpenagatik, eta 1.500 euro lizentziagatik. Faktura bakarra egingo da, entregaren onarpenaren ondoren, eta 30 egunetan banku-transferentziaz ordainduko da.')
replace('Lau egileen baimena eta, dagokionean, hasierako kodearen, ikastetxearen edo hirugarrenen eskubideak egiaztatu behar dira. Taldeak ezin ditu bereak ez diren eskubideak eman. Egile guztien sinadurarik edo ordezkaritza egokirik gabe, ez da talde osoaren baimenik dagoela adieraziko.',
        'Jefrysek bere kodearen ustiapen-eskubideak mantentzen ditu. ARAKAINek lizentzia ez-esklusiboa jasotzen du, epe mugagabean eta mundu osoan, barne-erabilerarako. Iturburu-kodearen entregak ez du eskubide guztien salmentarik eragiten. Jefrysek bere ekarpenak lizentziatzeko eskubideak izan behar ditu, hirugarrenenak errespetatuta.')
replace('AI4I 2020 datu-multzoa sintetikoa da eta UCI-k CC BY 4.0 lizentziarekin eskaintzen du. Egilea (Stephan Matzka), izenburua, UCI jatorria, DOI 10.24432/C5HS5C eta lizentzia adieraziko dira; egindako egokitzapenak ere identifikatuko dira. Enpresaren datuetarako baimenak ez du UCIren lizentzia ordezten.',
        'ARAKAINen datu historikoak eta zuzeneko telemetria bezeroaren informazio konfidentziala dira. Jefrysek kontratatutako lana egiteko soilik erabiliko ditu; ez ditu argitaratuko, salduko edo beste bezeroen ereduak entrenatzeko erabiliko. Beste jatorri bateko datu edo osagaiak gehituz gero, haien baimenak aparte egiaztatuko dira.')
replace('ez dago simulazio honetan baimenduta','ez dago kontratu honetan baimenduta')
replace('ARAKAIN Makineriak [forma juridikoa, IFZ eta helbidea], [ordezkariaren izena eta kargua] bidez, eta D Taldeko egileak: Igor Alfaro, Egoitz Urrutia, Asier Carabantes eta Asier Vieira [identifikazioa eta jakinarazpen-helbidea], honako baldintzak adosten dituzte. Ikastetxea kontratu-alderdi bada, haren izen juridikoa eta ordezkari baimendua ere jasoko dira.',
        'Bezeroa: ARAKAIN Makineriak [izen juridikoa, IFZ eta helbidea], [ordezkaria eta kargua] bidez. Hornitzailea: Jefrys [izen juridikoa, IFZ eta helbidea], [ordezkaria eta kargua] bidez. Alderdiek CNC Guard garatzeko eta ezartzeko zerbitzuari lotutako baldintza hauek adosten dituzte.')
replace('CNC Guard pilotua garatu eta ebaluatzeko soilik','CNC Guard garatu, entrenatu, balidatu eta ezartzeko soilik')
replace('2. Eremua eta iraupena. Pilotua [hasiera] eta [amaiera] artean egingo da, gehienez 90 egunez.',
        '2. Eremua eta iraupena. Hasierako ezarpen-zerbitzua [hasiera] eta [amaiera] artean egingo da, gehienez 90 egunez. Epe horren ondorengo sarbideak mantentze-akordio bereizia behar du.')
replace('pilotuko ingestiorako','zerbitzuko ingestiorako')
replace('Argitalpen akademikoetan datu sintetikoak edo benetan anonimoak erabiliko dira; enpresaren isilpeko emaitzek aurretiazko idatzizko baimena beharko dute.',
        'Jefrysek ez du bezeroaren daturik edo emaitzarik argitaratuko. ARAKAINen aurretiazko idatzizko baimena beharko da kanpoko erakustaldi, txosten edo erreferentzia komertzial baterako.')
replace('edo pilotua amaitzen bada','edo zerbitzua amaitzen bada')
replace('Lau egileen sinadurak edo ordezkaritza frogatua','Jefrysen ordezkariaren sinadura')
replace('Eragilea: [kontratatzeko gaitasuna duen erakundea edo lau kideak, identifikazio eta ordezkaritzarekin]. Ikastetxeak benetan kudeatzen badu tratamendua, haren rol eta identitatea kontratuan islatu beharko dira.',
        'Eragilea: Jefrys [izen juridikoa, IFZ, helbidea, ordezkaria eta kontaktua]. ARAKAINek tratamenduaren helburuak eta jarraibideak erabakitzen ditu; Jefrysek haren kontura jarduten du.')
replace('CNC Guard pilotuaren','CNC Guard zerbitzuaren')
replace('Simulaziorako edukia','Adostutako edukia')
replace('Pilotuan zehar, gehienez 90 egun','Hasierako zerbitzuan, gehienez 90 egun')
replace('Lizentzia-emaileak: Igor Alfaro, Egoitz Urrutia, Asier Carabantes eta Asier Vieira, D Taldeko egile gisa, beren eskubideen esparruan eta [identifikazioa, helbidea eta ordezkaritza]. Lizentzia-hartzailea: ARAKAIN Makineriak [IFZ, helbidea eta ordezkaria].',
        'Hornitzailea eta lizentzia-emailea: Jefrys [izen juridikoa, IFZ, helbidea eta ordezkaria]. Bezeroa eta lizentzia-hartzailea: ARAKAIN Makineriak [izen juridikoa, IFZ, helbidea eta ordezkaria].')
replace('2. Izaera eta prezioa. Doako lizentzia ez-esklusiboa ematen da, mundu osoan eta epe mugagabean, enpresaren barne-jarduerarako. Kontraprestazio ekonomikoa 0 eurokoa da simulazio honetan. Ez dago ustiapen-eskubide guztien salmentarik, esklusibotasunik edo egiletzaren eskualdaketarik. Lizentzia egile guztiek edo behar bezala baimendutako ordezkariak sinatzean izango da eraginkorra.',
        '2. Prezioa eta ordainketa. Prezio osoa 6.000 euro da, BEZa aparte: garapena eta ezarpena, 4.500 euro; ordainpeko lizentzia, 1.500 euro. Entrega onartu ondoren faktura bakarra jaulkiko da eta 30 egunetan transferentziaz ordainduko da. Ez dago hileko kuotarik. Lizentzia ez-esklusiboa, mundu osorakoa eta epe mugagabekoa da, barne-erabilerarako; ez da eskubide guztien salmenta. Behin betiko lizentzia ordainketa osoarekin aktibatuko da; onarpen-probetarako aldi baterako erabilera baimentzen da.')
replace('10. Erabilera aurreikusia. CNC Guard mantentze-lanetarako laguntza-prototipoa da.',
        '10. Erabilera aurreikusia. CNC Guard ARAKAINen mantentze-lanetarako laguntza-sistema da.')
replace('11. Bermea eta mantentzea. Entregaren irismena manifestuko funtzio eta mugak dira; ez da zero akats, aurrezki zehatz edo etengabeko erabilgarritasun bermerik adosten. Laguntza, eguneraketak, zerbitzu-mailak eta ekoizpeneko mantentzea beste akordio batean zehaztu beharko dira. Alderdiek beren jarduera eta aldaketen ardura izango dute, lege aplikagarriaren arabera; ez dira baztertzen legez baztertu ezin diren erantzukizunak.',
        '11. Onarpena eta bermea. ARAKAINek 10 lanegun izango ditu entrega probatu eta adostutako baldintzen ez-betetzeak idatziz azaltzeko. Jefrysek akatsak zuzendu eta onarpen-akta sinatuko da. Prezioak 90 eguneko akats-zuzenketa barne hartzen du onarpenetik, entregatutako bertsioak adostutakoa bete dezan. Ez du funtzio berririk edo etengabeko mantentzerik barne hartzen. Horiek aparte kontratatuko dira; ez dira baztertzen legez baztertu ezin diren erantzukizunak.')
replace('Lau lizentzia-emaileen sinadurak edo ordezkaritza frogatua','Jefrysen ordezkariaren sinadura')
replace('Datuen CC BY 4.0 atribuzioa mantenduko da.','Bezeroaren datuak ez daude lizentzia publiko baten pean; erabilera 6.9 akordioak mugatzen du.')
replace('Jasotzailearen eta egileen sinadurak','ARAKAINen eta Jefrysen ordezkarien sinadurak')
replace('[pilotua eta amaiera-data]','[zerbitzua eta amaiera-data]')
replace('Kontratu-ereduak proiekturako idatzitako simulazioak dira; ez dira agintaritza batek onartutako kontratu ofizialak.',
        'Kontratu-eranskinek ARAKAIN bezeroaren eta Jefrys hornitzailearen arteko harremana, zerbitzuaren prezioa eta erabilera-baldintzak jasotzen dituzte.')
replace('@@ [8] Stephan Matzka (2020), AI4I 2020 Predictive Maintenance Dataset, UCI, DOI 10.24432/C5HS5C. Datu sintetikoak, CC BY 4.0: https://doi.org/10.24432/C5HS5C ; lizentzia: https://creativecommons.org/licenses/by/4.0/',
        '@@ [8] Proiektuko datuen jatorria: ARAKAIN Makineriak enpresaren CNC makinen telemetria eta matxuren historikoa. Jefrysen erabilera-baimena 6.9 akordioan jasotzen da; datuak ez dira publikoki banatzen.')
replace('Aldaketa horiek balioztatu gabe, entregak prototipoaren irismena izango du; ez da ekoizpeneko erabilera segurua edo legezko adostasuna ziurtatutzat emango.',
        'ARAKAINek eta Jefrysek entrega- eta onarpen-akta sinatuko dute. Sinatutako akordioek, probek eta egiaztatutako kontrolek osatuko dute zerbitzua ekoizpenean erabiltzeko dokumentazioa; txostenak bakarrik ez du adostasun-ziurtagiririk ordezten.')
replace("'CNC Guard - Dokumentazioa - D Taldea','/Author':'D Taldea','/Subject':'Segurtasuna, etika, lege-betetzea eta kontratu simulatuak'", "'CNC Guard - Dokumentazioa - Jefrys','/Author':'Jefrys','/Subject':'ARAKAIN eta Jefrys - Segurtasuna, lege-betetzea eta zerbitzu-kontratuak'")

# Consistent company naming, keeping the unrelated machine-group terminology intact.
for old,new in [('D Taldearen','Jefrysen'),('D Taldeak','Jefrysek'),('taldearen','Jefrysen'),('taldeak','Jefrysek'),('Taldeak','Jefrysek'),('Taldearen','Jefrysen'),('taldeari','Jefrysi'),('talde osoaren','Jefrys enpresaren'),('talde osoa','Jefrys enpresa')]:
    s=s.replace(old,new)
s=s.replace('SIMULAZIO AKADEMIKOA - ','Kontratu-eranskina - ')
s=s.replace('taldearenak','Jefrysenak')
s=s.replace('Jatorrizko taldearen','Jefrysen')
s=s.replace('Jatorrizko Jefrysen','Jefrysen')
s=s.replace('CNC Guard pilotua','CNC Guard ezarpena')
s=s.replace('pilotua amaitzean','zerbitzua amaitzean')
s=s.replace('pilotu','ezarpen-zerbitzu')
s=s.replace('Enpresak eta taldeak','ARAKAINek eta Jefrysek')
s=s.replace('enpresaren eta taldearen','ARAKAINen eta Jefrysen')
s=s.replace('Enpresaren eta Jefrysen','ARAKAINen eta Jefrysen')
s=s.replace('Jefrysen berariazko','Jefrysen berariazko')
s=s.replace('egileen aurretiazko idatzizko baimenik gabe','Jefrysen aurretiazko idatzizko baimenik gabe')

# Make source conclusions describe the same company data flow.
s=s.replace("t=re.sub(r'\\s+',' ',t).strip()", "t=re.sub(r'\\s+',' ',t).strip()\n    t=t.replace('simulagailuak sortutako CSV fitxategiak','ARAKAINen CNC makinek sortutako CSV fitxategiak')")
# Apply precisely scoped amendments to source pages while retaining their layout.
s=s.replace('r=PdfReader(SOURCE)', 'r=PdfReader(SOURCE)\nfrom patch_original_pages import revise_original_pages\nrevise_original_pages(r)')
p.write_text(s,encoding='utf-8')
print('Business-case corrections applied.')
