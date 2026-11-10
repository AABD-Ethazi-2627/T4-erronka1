from pathlib import Path
from io import BytesIO
import json, re
from html import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from pypdf import PdfReader, PdfWriter

ROOT=Path(__file__).resolve().parents[2]
TMP=ROOT/'tmp/pdfs'
OUT=ROOT/'output/pdf/Dokumentazioa - Jefrys - Segurtasuna eta lege-betetzea.pdf'
SOURCE=Path(r'C:\Users\vieira.asier\Downloads\Dokumentazioa - D Taldea.pdf')
pdfmetrics.registerFont(TTFont('Arial',r'C:\Windows\Fonts\arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold',r'C:\Windows\Fonts\arialbd.ttf'))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='Arial-Bold',italic='Arial',boldItalic='Arial-Bold')
r=PdfReader(SOURCE)
from patch_original_pages import revise_original_pages
revise_original_pages(r)
W,H=map(float,[r.pages[4].mediabox.width,r.pages[4].mediabox.height])
styles={
 'body':ParagraphStyle('body',fontName='Arial',fontSize=10.5,leading=13.5,spaceAfter=7,alignment=TA_JUSTIFY),
 'title':ParagraphStyle('title',fontName='Arial',fontSize=17,leading=20,spaceAfter=13),
 'h':ParagraphStyle('h',fontName='Arial',fontSize=12.5,leading=16,spaceBefore=6,spaceAfter=8,keepWithNext=True),
 'small':ParagraphStyle('small',fontName='Arial',fontSize=9,leading=12,spaceAfter=7),
 'cell':ParagraphStyle('cell',fontName='Arial',fontSize=9.5,leading=12.5),
}
pages=[]
def add(title,body): pages.append((title,body.strip()))

add('6. Segurtasuna, etika eta lege-betetzea', '''
## 6.1 Sarrera eta datuen erabilerari buruzko erabakia
CNC Guard proiektuan, segurtasuna eta lege-betetzea datuen bizi-ziklo osoan hartu behar dira kontuan: CSV fitxategiak jasotzean, NiFi-n prozesatzean, ereduak entrenatzean eta Kibana-n emaitzak erakustean. Helburua datuen konfidentzialtasuna, osotasuna eta erabilgarritasuna babestea da, pertsonen eskubideekin eta giza gainbegiraketarekin batera.
ARAKAIN Makineriak enpresak Jefrys kontratatu du CNC Guard garatu eta ezartzeko. Proiektuko telemetria ARAKAINen CNC makinen produkzio-datuak dira. ai4i2020_train.csv fitxategiak enpresak emandako datu historikoak biltzen ditu, eta etengabeko CSV fluxuak makinen uneko neurketak jasotzen ditu.
## 6.1.1 ARAKAIN eta Jefrys enpresen arteko harremana
ARAKAIN Makineriak Jefrysi bere telemetria eskuratzeko eta erabiltzeko baimen mugatua ematen dio, kontratatutako garapena, entrenamendua, balidazioa eta ezarpena egiteko. Enpresak datuen kontrola eta dagozkion eskubideak mantentzen ditu. Ez da datu-basearen salmentarik, erabilera librerik edo beste bezero batzuentzako berrerabilpen-baimenik ematen.
Softwareari dagokionez, ordainpeko erabilera-lizentzia ez-esklusiboa ematen da, iturburu-kodea entregatuta. Garapenaren, ezarpenaren eta lizentziaren prezio osoa 6.000 euro da, BEZa aparte, ordainketa bakarrean. Enpresak bere barne-erabilerarako exekutatu, kopiatu eta aldatu ahal izango du. Ez zaizkio Jefrysen ustiapen-eskubide guztiak saltzen. Baldintza zehatzak 6.11 atalean jasotzen dira.
## 6.1.2 Enpresak emandako datuak
| Datu-mota | Proiektuan emango zaion tratamendua |
| ARAKAINen datu historikoak | Entrenamendurako eta balidaziorako erabilera mugatua; ez dira Jefrysen jabetza bihurtzen. |
| Enpresaren benetako telemetria | 6.9 akordioa sinatu; helburu mugatua eta konfidentzialtasuna aplikatu. |
| Kontuak, IP helbideak edo langileei lotutako datuak | GDPR aztertu; enpresaren kontura sarbidea badago, 6.10 kontratua aktibatu. |
Kontratu-eranskinetan bezeroa ARAKAIN Makineriak da, eta hornitzailea Jefrys. IFZ, helbide, ordezkari eta sinadura eremuak formalizazioan beteko dira. Datuak eskuratzeko baimena zerbitzu-kontratuari lotuta dago; ez da datuen titulartasunaren lagapena.
''')

add('6.2 Datu pertsonalen babesa: GDPR', '''
Erreferentzia nagusia 2016/679 (EB) Erregelamendua da, Datuak Babesteko Erregelamendu Orokorra (GDPR/DBEO). Espainiako 3/2018 Lege Organikoa ere kontuan hartzen da. GDPR pertsona fisiko identifikatu edo identifikagarriei buruzko informazioari aplikatzen zaio; industria-datu guztiak ez dira automatikoki datu pertsonalak.
## 6.2.1 Proiektuari nola aplikatzen zaion
Tenperatura, RPM, momentua eta erremintaren higadura, berez, makina bati buruzko datuak dira. Hala ere, machine_id eta timestamp eremuak txanda edo langileen esleipenekin gurutzatzen badira, pertsona bat identifikatzeko aukera egon daiteke. Kontu izendunak, sarbide-erregistroak eta IP helbideak ere datu pertsonalak izan daitezke.
Makina-identifikatzailea ordeztea ez da beti anonimizazioa. Enpresak lotura-taula badu edo beste bide batetik pertsona identifika badaiteke, datuak pseudonimizatuta egongo dira eta GDPR aplikatzen jarraituko da. Anonimizazioak berridentifikazioa arrazoizko bitartekoekin eragotzi behar du.
## 6.2.2 Bete beharreko printzipioak
| Printzipioa | CNC Guard proiektuko aplikazioa |
| Zilegitasuna, leialtasuna eta gardentasuna | Tratamendu bakoitzaren oinarri juridikoa identifikatu eta interesdunei informazioa eman. |
| Helburuaren mugaketa eta minimizazioa | Mantentze-lanetarako behar diren datuak soilik hartu; langileen produktibitate-profilak baztertu. |
| Zehaztasuna | Balio okerrak, erregistro bikoiztuak eta denbora-zigilu desegokiak kontrolatu. |
| Kontserbazioaren mugaketa | 6.6 ataleko epeak aplikatu eta ezabaketa egiaztatu. |
| Osotasuna, konfidentzialtasuna eta erantzukizuna | Sarbide mugatuak, zifratzea eta egindako kontrolen frogak gorde. |
## 6.2.3 Rolak eta oinarri juridikoa
Enpresak helburuak eta funtsezko bitartekoak erabakitzen baditu, tratamenduaren arduraduna izango da. Jefrysek haren jarraibideekin datu pertsonalak kudeatzen baditu, tratamendu-eragilea izango da; rol horiek benetako jardueraren arabera zehaztuko dira, ez kontratuaren izenagatik bakarrik.
Segurtasuneko kontu eta logetarako, enpresa pribatuak interes legitimoa azter dezake, beharrezkotasuna eta eskubideen haztapena idatziz eginda. Laneko baimena ez da oinarri orokor gisa erabiliko. ARAKAINen eta Jefrysen kontratuak ez du berez langileen datuak tratatzeko oinarri juridikorik sortzen.
''')

add('6.3 Adimen artifizialaren araudia: AI Act', '''
Bigarren arau nagusia 2024/1689 (EB) Erregelamendua da, AI Act izenez ezagutzen dena. Arriskua sistemaren aurreikusitako helburuaren eta erabileraren arabera ebaluatzen da; Machine Learning erabiltzeak bakarrik ez du sistema arrisku handiko bihurtzen.
## 6.3.1 CNC Guard sistemaren hasierako sailkapena
Dokumentatutako erabileran, CNC Guard-ek makinen neurketak aztertzen ditu eta mantentze-langileentzako alertak sortzen ditu. Ez du langilerik sailkatzen, ezta makina fisikoki kontrolatzen ere. Hasierako azterketan, erabilera horrek ez du berez III. eranskineko arrisku handiko kasurik erakusten. Ondorio hori erabilera mugatu horretarako arrazoiketa da, ez ziurtagiri bat.
Makinen segurtasun-osagai gisa integratuko balitz, 6.1 artikuluko bi baldintzak aztertu beharko lirateke: I. eranskineko produktu baten segurtasun-osagaia edo produktua izatea, eta dagokion sektore-araudiak hirugarren baten adostasun-ebaluazioa eskatzea. Makinak erabiltzea ez da, berez, baldintza horiek betetzea.
Langileen errendimendua, lanen banaketa edo enplegu-erabakiak ebaluatzeko erabiltzea beste helburu bat litzateke; III. eranskina eta GDPR berriro aztertu beharko lirateke. Erabilera hori ez da proiektu honetako lizentzian baimentzen.
## 6.3.2 Betebeharrak eta erabilera-mugak
Jefrys CNC Guard-en hornitzailea da, eta ARAKAIN Makineriak sistema erabiltzen duen enpresa hedatzailea. Jefrysek aurreikusitako helburua, bertsioa eta erabilera-jarraibideak dokumentatuko ditu; ARAKAINek baimendutako erabilera eta giza gainbegiraketa bermatuko ditu. Produkzioan jarri aurretik sailkapena eta aplikagarri diren betebeharrak berrikusiko dira.
Ereduaren bertsioa, entrenamenduko datuen jatorria, metrikak, mugak eta atalaseak erregistratuko dira. Erabiltzaileek alerta bat nola interpretatu ikasiko dute. Arrisku handiko erabilera bihurtuz gero, arriskuen kudeaketa, dokumentazio teknikoa, datuen gobernantza, erregistroak eta adostasun-prozedura aplikagarriak egiaztatuko dira.
## 6.3.3 Aplikazio-egutegia
2026/11/09an kontsultatutako Europako Batzordearen informazioaren arabera, aplikazio orokorraren data 2026/08/02 da; 2026ko AI Omnibus aldaketaren ondoren, III. eranskineko arrisku handiko sistemen epea 2027/12/02ra eta produktu arautuetan txertatutakoena 2028/08/02ra luzatu da. Ekoizpenera igaro aurretik testu indarduna berrikusiko da [2-3].
Epe horiek ez dute lehendik aplikagarri den datu-babesa edo makinen segurtasunari buruzko araudia atzeratzen. CNC Guard ez da larrialdi-gelditzearen edo derrigorrezko segurtasun-mekanismoen ordezko gisa erabiliko.
''')

add('6.4 Gai etikoak eta giza gainbegiraketa', '''
Etikaren helburua ez da legea aipatzea bakarrik. Sistemak huts egiten duenean norengan eta nola eragiten duen aztertu behar da. CNC Guard-en, huts egindako iragarpenek mantentze-lanetan, ekoizpenean eta langileen segurtasunean eragin dezakete.
## 6.4.1 Alborapena eta ebaluazio egokia
Entrenamendu-multzoan, 8.000 erregistroetatik 271 matxurak dira (%3,39). Beti matxurarik ez dagoela esango lukeen eredu batek accuracy handia izango luke, baina matxurak ez lituzke detektatuko. Horregatik, recall, precision, F1 eta konfusio-matrizea batera aztertzen dira.
4.5 atalean jasotako testean, 54 matxuretatik 45 detektatu dira; 9 ez dira detektatu eta 61 alarma faltsu sortu dira. Horrek ez du segurtasun industriala bermatzen. Balidazioan aukeratutako %16ko erabaki-atalasea ezin da aldatu ondorioak berriro ebaluatu gabe; ez da zuzenean pantailako alerta-mailen ehunekoekin nahastu behar.
H, M eta L makinen taldeetan, matxura mota bakoitzean eta lan-baldintza desberdinetan recall, FNR eta FPR aztertzea aurreikusten da, lagin-kopuruarekin batera. Talde horiek makina-taldeak dira, ez pertsonen kategoria demografikoak. Lagin gutxiko emaitzek duten ziurgabetasuna adieraziko da; ez da oraindik egin gabeko auditoriarik gainditutzat emango.
## 6.4.2 Gardentasuna eta erantzukizuna
Arduradunak LARRIA alerta aztertuko du, sentsoreen balioak eta datuen freskotasuna egiaztatuko ditu eta mantentze-protokoloaren arabera erabakiko du. Sistemak ez du makina automatikoki geldituko. Erabakia, arrazoia, eredua eta erabilitako datuen unea erregistratuko dira.
4.9 atalean azaltzen denez, ereduak uneko neurketekin lotutako matxura-egoera aztertzen du; ez du matxura zenbat ordu barru gertatuko den kalkulatzen. Interfazeak eta kontratuek muga hori errespetatu behar dute. Aldagaien garrantziak azalpen orokorra laguntzen du, baina ez du kausalitatea frogatzen.
## 6.4.3 Beste eragin batzuk
Telemetria ez da langileak zaintzeko, zigortzeko edo produktibitate-rankingak egiteko erabiliko. GDPRren 22. artikulua pertsonengan ondorio juridikoak edo antzeko eragin esanguratsuak dituzten erabaki guztiz automatizatuekin lotzen da; makina bati buruzko alerta ez da berez kasu hori.
Eredu berriak datu adierazgarriekin eta test independentearekin balidatuko dira. Entrenamendu errepikatu alferrikakoak eta datuen kopia gehiegi saihestuko dira, energia eta biltegiratzea murrizteko. Deepfake-ak eta prompt injection ez dira egungo arkitekturaren arrisku nagusiak, ez baita LLMrik edo eduki-sorkuntzarik erabiltzen.
''')

add('6.5 Segurtasuna diseinutik', '''
2.8 atalak SMB karpetaren irakurketa soileko sarbidea eta .env fitxategia GitHub-era ez igotzea aipatzen ditu. Neurri horiek abiapuntua dira. Hemen jasotako gainerako kontrolak ekoizpenerako eskakizunak dira; dokumentu hau idazteak ez du haien ezarpena edo probak eginda daudela esan nahi.
| Arriskua / osagaia | Aurreikusitako kontrola | Egiaztapenaren froga |
| SMB / jatorrizko CSVak | Irakurtzeko soilik; kontu espezifikoa; sare fidagarria; SMB zifratzea edo tunela behar denean. | Idazketa ukatua eta sarbide-baimenen berrikuspena. |
| Kontuak eta sekretuak | Banakako kontuak, gutxieneko baimenak, administrazioan MFA ahal denean; sekretu-biltegi zifratua eta txandakatzea. | Baimenen matrizea; sekreturik gabeko Git historia. |
| Kafka eta Docker sarea | Behar diren zerbitzuak soilik argitaratu; suebakia; autentifikazioa, ACLak eta TLS egokiak. | Baimenik gabeko producer/consumer bati sarbidea ukatzea. |
| NiFi eta FastAPI | HTTPS; ziurtagiriak balidatu; API tokena; sarrera-eskema, tamaina eta tasa mugatu. | Tokenik gabe 401/403; sarrera okerrak 4xx. |
| Elasticsearch, Kibana eta MongoDB | Autentifikazioa, rolak, administratzaile-kontu bereiziak eta kanporako sarbide mugatua. | Ikusleak ezin du idatzi edo indizerik ezabatu. |
| Datuen pozoitzea eta manipulazioa | Jatorria, eskema, unitateak, denbora-zigiluak eta bikoiztuak kontrolatu; balio anomaloak berrikusi. | Baliozko/okerreko datuen probak eta baztertze-erregistroa. |
| Modeloa ordeztea / kode-exekuzioa | .pkl fidagarriak soilik kargatu; modeloa irakurtzeko soilik; hash edo sinadura; bertsioen kontrola. | Aldatutako artefaktua ez da onartzen; aurreko bertsiora itzul daiteke. |
| Datu-galera eta zerbitzu-etena | Babeskopia zifratuak, osasun-kontrolak, alerta teknikoak eta leheneratze-probak. | Leheneratze-probaren data eta lortutako denborak. |
Joblib/pickle fitxategiak kargatzeak kodea exekuta dezake: ez dira kanpoko fitxategi ezezagunak kargatuko. HTTPS erabiltzeak ez du laguntzen ziurtagiria egiaztatzen ez bada. Docker sare berean egoteak ere ez du autentifikazioa ordezten.
Kontrolen egoera, arduraduna, data eta froga 6.13 ataleko erregistroan bilduko dira. Segurtasun-probak baimendutako ingurune isolatuan egingo dira, produkzioko makinetan esku hartu gabe.
''')

add('6.6 Kontserbazioa eta gorabeheren kudeaketa', '''
## 6.6.1 Zerbitzuaren kontserbazio-politika
Ondoko epeak proiekturako proposatutako mugak dira; ez dira legeak datu guztientzat ezarritako epe orokorrak. Enpresak beharrezkotasuna eta legezko betebeharrak berrikusiko ditu benetako tratamendua hasi aurretik.
| Informazioa | Proposatutako epea eta amaierako ekintza |
| Enpresaren CSVak eta Jefrysen lan-kopiak | Hasierako ezarpen-zerbitzuan, gehienez 90 egun; amaitzean itzuli eta 30 egunetan ezabatu. |
| Telemetria eta iragarpen operatiboak | 90 egun; gero ezabatu edo benetan anonimizatutako agregatuak soilik mantendu. |
| Kontu eta sarbide-logak | 90 egun; gorabehera justifikatu baten frogak bereizita eta behar den epe mugatuan. |
| MongoDBko erroreak eta NiFi provenance/ilarak | 30 egun; ez gorde pasahitzik, tokenik edo payload pertsonal osoak beharrezkoa ez bada. |
| Babeskopiak | 30 eguneko txandaketa; ezabatutako datuak ez dira erabilera arruntera berreskuratuko. |
| Kontratuak, lizentzia eta entrega-aktak | Datu operatiboetatik bereizita, betebeharrak eta erreklamazio-epeak betetzeko behar den denboran. |
Politikak CSV kopiak, Kafka retention, NiFi repositorioak, Elasticsearch indizeak, MongoDB, notebook irteerak eta babeskopiak hartzen ditu. Bolumen iraunkor bat edukitzea ez da babeskopia izatea. Leheneratuz gero, amaitutako ezabaketak berriro aplikatuko dira.
## 6.6.2 Gorabehera baten aurrean jardutea
1. Antzeman eta erregistratu: data/ordua, zerbitzuak, eraginpeko datuak, larritasuna eta lehen ebidentziak bildu; ez zabaldu sekreturik gorabehera-fitxan.
2. Eduki: konprometitutako kontua edo zerbitzua isolatu, tokenak txandakatu eta aldaketak geldiarazi. Makinaren eragiketa segurua enpresako arduradunak erabakiko du.
3. Jakinarazi: Jefrysek enpresari bidegabeko atzerapenik gabe jakinaraziko dio; kontratuko jakinarazpen-epea gehienez 24 ordukoa da, jakin duenetik. Ez da ikerketa amaitu arte itxarongo.
4. Arriskua baloratu: datu pertsonalen urraketa bada, arduradunak agintaritza eskudunari 72 orduko epean jakinaraztea baloratuko du, jakin duenetik, eskubideetarako arriskua izatea nekez gertatzekoa denean izan ezik. Arrisku handia badago, interesdunei ere bidegabeko atzerapenik gabe jakinaraziko die, 34. artikuluko salbuespenak kontuan hartuta.
5. Berreskuratu eta ikasi: kopia fidagarritik leheneratu, balidatu, arrazoia zuzendu eta gertatutakoa dokumentatu, baita agintaritzari ez jakinarazteko arrazoia ere, halakorik badago.
''')

add('6.7 Softwarearen titulartasuna eta erabilera', '''
## 6.7.1 Aukeratutako eredua
Jefrysek CNC Guard garatu eta ezartzeko zerbitzua eta ordainpeko lizentzia eskaintzen dizkio ARAKAIN Makineriak enpresari. Prezio osoa 6.000 euro da, BEZa aparte: 4.500 euro garapen eta ezarpenagatik, eta 1.500 euro lizentziagatik. Faktura bakarra egingo da, entregaren onarpenaren ondoren, eta 30 egunetan banku-transferentziaz ordainduko da.
Jefrysek bere kodearen ustiapen-eskubideak mantentzen ditu. ARAKAINek lizentzia ez-esklusiboa jasotzen du, epe mugagabean eta mundu osoan, barne-erabilerarako. Iturburu-kodearen entregak ez du eskubide guztien salmentarik eragiten. Jefrysek bere ekarpenak lizentziatzeko eskubideak izan behar ditu, hirugarrenenak errespetatuta.
## 6.7.2 Enpresak egin dezakeena
| Ekintza | Lizentzian aurreikusitakoa |
| Exekutatu eta instalatu | Bai, enpresaren barne-inguruneetan eta beharrezko kopietan. |
| Iturburu-kodea aldatu | Bai, bere beharretara egokitzeko; aldaketak eta egileak identifikatuta. |
| Eredua berrentrenatu | Bai, erabiltzeko eskubidea duen datuekin eta balidazio berriaren ondoren. |
| Mantentze-enpresa bati sarbidea eman | Bai, enpresaren izenean soilik, konfidentzialtasunarekin eta lizentziaren mugak betez. |
| Beste bezero bati saldu edo banatu | Ez, Jefrysen berariazko idatzizko baimen berririk gabe; hirugarrenen lizentziek aitortutako eskubideak errespetatuz. |
| Jefrysen izenean aldaketak argitaratu | Ez; jatorrizko bertsioa eta enpresak aldatutakoa bereizi behar dira. |
## 6.7.3 Hirugarrenen teknologiak eta datuak
Docker, Filebeat, Kafka, NiFi, FastAPI, scikit-learn, Elasticsearch, Kibana eta MongoDB ez dira Jefrysen jabetzakoak. Erabilitako bertsio eta banaketa bakoitzaren lizentzia identifikatuko da; ez da osagai guztiak lizentzia berekoak direla esango. Doakoa izateak ez du banatzeko edo SaaS moduan eskaintzeko baimen osoa esan nahi.
ARAKAINen datu historikoak eta zuzeneko telemetria bezeroaren informazio konfidentziala dira. Jefrysek kontratatutako lana egiteko soilik erabiliko ditu; ez ditu argitaratuko, salduko edo beste bezeroen ereduak entrenatzeko erabiliko. Beste jatorri bateko datu edo osagaiak gehituz gero, haien baimenak aparte egiaztatuko dira.
Entregan kodea, eredua, konfigurazio-txantiloiak, fluxuak, dashboard-ak, dokumentazioa eta lizentzia-inbentarioa sartuko dira. Benetako pasahitzak eta enpresaren datuak ez dira entrega publikoan sartuko.
''')

add('6.8 Legezko dokumentazioa eta lan-prozedura', '''
Enpresaren datuak erabiltzeko baimena, konfidentzialtasuna, datu pertsonalen tratamendu-enkargua eta softwarearen lizentzia gauza desberdinak dira. Dokumentu bakarrak ez ditu beste guztiak ordezten.
| Dokumentua | Noiz behar den eta zertarako |
| 6.9 Datuen erabilera eta konfidentzialtasun-akordioa | Benetako telemetria jaso aurretik; datu-motak, helburua, sarbideak eta ezabaketa mugatzeko. |
| 6.10 Tratamendu-enkarguaren kontratua | Jefrysek enpresaren kontura datu pertsonalak eskuratu edo tratatzen baditu; GDPRren 28. artikuluko baldintzak ezartzeko. |
| 6.11 Softwarearen erabilera-lizentzia | Kodea eta modeloa entregatzean; erabilera, aldaketak, banaketa eta erantzukizunak argitzeko. |
| 6.12 Pribatutasun-informazioa | Kontuak edo log pertsonalak biltzen hasi aurretik; interesdunei tratamendua azaltzeko. |
| 6.13 Entrega-, kontrol- eta ezabaketa-aktak | Baimenen, proben eta proiektuaren amaieraren frogak gordetzeko. |
## 6.8.1 Datu errealak jaso aurreko urratsak
Lehenik, datuen jatorria eta titularren eskubideak egiaztatuko dira. Ondoren, identifikagarritasunaren azterketa egingo da: telemetriak pertsonak identifikatzeko aukera ematen duen, beste taula batzuekin lotu daitekeen eta logetan zer biltzen den jasoko da.
Datuak benetan anonimoak badira, 6.9 akordioa aplikatuko da, eta erabakia dokumentatuko da. Jefrysek enpresaren datu pertsonalak tratatuko baditu, 6.10 kontratua ere sinatuko da eta 6.12 informazioa emango da. Jefrysek bere helburu propioetarako erabiltzea ez da enkargu gisa ezkutatuko: beste zilegitasun- eta rol-azterketa bat eskatzen du, eta ez dago kontratu honetan baimenduta.
## 6.8.2 Eragin-ebaluazioa eta aldaketen kontrola
GDPRren 35. artikuluaren arabera, aurreikusitako tratamenduak pertsonen eskubideetarako arrisku handia izan badezake, datu-babesaren gaineko eragin-ebaluazioa egingo da tratamendua hasi aurretik. IA erabiltzeak bakarrik ez du kasu guztietan ebaluazioa derrigorrezko egiten. Langileen jarraipena, eskala eta datuen loturak aztertuko dira; hondar-arrisku handia bada, 36. artikuluko aurretiazko kontsulta baloratuko da.
Makina berriak, datu pertsonal berriak, hodeiko hornitzaile bat edo automatikoki jarduteko gaitasuna gehitzeak berrikuspena eskatuko du. Ez da erabilera berririk hasiko kontratuak, arriskuen azterketa eta segurtasun-kontrolak egokitu arte.
''')

add('6.9 Datuen erabilera eta konfidentzialtasun-akordioa', '''
Kontratu-eranskina - A eredua - Sinatu gabe
## Alderdiak eta objektua
Bezeroa: ARAKAIN Makineriak [izen juridikoa, IFZ eta helbidea], [ordezkaria eta kargua] bidez. Hornitzailea: Jefrys [izen juridikoa, IFZ eta helbidea], [ordezkaria eta kargua] bidez. Alderdiek CNC Guard garatzeko eta ezartzeko zerbitzuari lotutako baldintza hauek adosten dituzte.
1. Baimena. Enpresak telemetria eskuratzeko eta erabiltzeko baimen ez-esklusiboa ematen du, CNC Guard garatu, entrenatu, balidatu eta ezartzeko soilik. Ez du datuen titulartasuna edo ustiapen orokorrerako eskubiderik eskualdatzen. Baimendutako datuak: makina-kodea, mota, neurketaren unea, tenperaturak, RPM, momentua, higadura eta matxura-etiketak; laginaren identifikazioa eta hash-a entrega-aktan jasoko dira.
2. Eremua eta iraupena. Hasierako ezarpen-zerbitzua [hasiera] eta [amaiera] artean egingo da, gehienez 90 egunez. Epe horren ondorengo sarbideak mantentze-akordio bereizia behar du. Datuak [EB/EEE barruko zerbitzariaren kokapena] ingurunean gordeko dira. Enpresak datu horiek emateko ahalmena duela egiaztatuko du. Datu pertsonalak antzemanez gero, sarbidea etengo da eta 6.10 kontratua aktibatu aurretik ez dira tratatuko.
3. Helburuak eta mugak. Baimena zerbitzuko ingestiorako, iragarpenetarako eta, berariaz jasota badago, enpresarentzako ereduaren balidazio edo berrentrenamendurako da. Ez dago baimenduta datuak saltzea, beste bezeroentzat erabiltzea, repositorio publikora igotzea, kanpoko AA zerbitzuetara bidaltzea edo lan-errendimendua ebaluatzea. Beste erabilera batek idatzizko akordio berria behar du.
4. Konfidentzialtasuna. Datu teknikoak, negozioari buruzko informazioa, konfigurazioak eta sekretuak isilpekoak dira. Sarbidea izendatutako eta konpromiso hau onartutako pertsonetara mugatuko da. Ez dira isilpeko izango legezkotasunez publiko diren edo modu independentean garatu direla frogatzen den informazioak. Legezko errekerimendu bat badago, beharrezkoa soilik emango da eta enpresari jakinaraziko zaio, legeak debekatzen ez badu.
5. Segurtasuna eta gorabeherak. 6.5 ataleko neurriak bete eta egiaztatuko dira. Gorabeherak bidegabeko atzerapenik gabe eta gehienez 24 ordutan jakinaraziko dira [enpresaren kontaktua] helbidera. Jefrysek ez du bezeroaren daturik edo emaitzarik argitaratuko. ARAKAINen aurretiazko idatzizko baimena beharko da kanpoko erakustaldi, txosten edo erreferentzia komertzial baterako.
6. Amaiera. Enpresak baimena eteten badu edo zerbitzua amaitzen bada, sarbideak kenduko dira. Datuak formatu erabilgarrian itzuliko dira eta lan-kopiak 30 egunetan ezabatuko dira; babeskopiak 30 eguneko txandan desagertuko dira. Enpresaren informazioa agerian uzten duen eredua ezin da berrerabili baimenik gabe. Ezabaketa-ziurtagiria entregatuko da; konfidentzialtasunak informazioa legez isilpekoa den bitartean iraungo du.
Lekua/data: [________]. Enpresaren ordezkaria: [________]. Jefrysen ordezkariaren sinadura: [________].
''')

add('6.10 Datu pertsonalen tratamendu-enkargua', '''
Kontratu-eranskina - B eredua - Sinatu gabe - 1/2
Akordio hau A ereduaren osagarria da eta Jefrysek enpresaren kontura datu pertsonalak tratatuko dituenean aplikatuko da. Benetan anonimoak diren datuetarako ez da enkargurik aktibatuko, baina kontu eta logetarako beharra bereizita aztertuko da.
## 6.10.1 Alderdiak, tratamendua eta jarraibideak
Arduraduna: ARAKAIN Makineriak [IFZ, helbidea, ordezkaria eta kontaktua]. Eragilea: Jefrys [izen juridikoa, IFZ, helbidea, ordezkaria eta kontaktua]. ARAKAINek tratamenduaren helburuak eta jarraibideak erabakitzen ditu; Jefrysek haren kontura jarduten du.
Objektua: CNC Guard zerbitzuaren euskarri teknikoan beharrezkoak diren kontuak, sarbideak eta diagnostikoa kudeatzea. Eragiketak: jasotzea, kontsultatzea, biltegiratzea, sarbidea mugatzea, babeskopia egitea eta ezabatzea. Ez da langileen profilaketarik edo enpresatik kanpoko entrenamendurik baimentzen.
| Kontratuaren eremua | Adostutako edukia |
| Interesdunak | Baimendutako erabiltzaileak eta mantentze- edo administrazio-langileak. |
| Datu pertsonalak | Laneko erabiltzaile-identifikatzailea, beharrezko kontaktua, IP helbidea eta sarbidearen data/ordua. |
| Baztertutako datuak | Kategoria bereziak, biometria, soldatak, diziplina-datuak eta langile bakoitzari lotutako telemetria. |
| Iraupena eta kokapena | Hasierako zerbitzuan, gehienez 90 egun; [EB/EEEko kokapen zehatza]. Amaierako epeak 6.6 eta 6.9 ataletan. |
1. Eragileak arduradunaren jarraibide dokumentatuen arabera jardungo du soilik, nazioarteko transferentziei dagokienez ere. Legeak beste tratamendu bat behartzen badu, aurretik jakinaraziko dio, legeak interes publikoko arrazoiengatik debekatzen ez badu. Jarraibideren bat GDPRren aurkakoa dela uste badu, berehala ohartaraziko du.
2. Sarbidea duten pertsonek konfidentzialtasun-konpromisoa edo legezko sekretu-betebeharra izango dute. Kontuak izendunak izango dira; alta eta baja baimenduak dokumentatuko dira. Eragileak ez ditu datuak bere helburuetarako erabiliko.
3. Eragileak GDPRren 32. artikuluaren araberako neurri egokiak ezarriko ditu: gutxieneko baimenak, komunikazioen zifratzea, babeskopien babesa, osotasuna eta erabilgarritasuna, leheneratzea eta kontrolen aldizkako egiaztapena. 6.5 eta 6.6 atalak segurtasun-eranskin gisa aplikatuko dira; ezarpenaren frogak erantsi beharko dira sarbidea hasi aurretik.
Kontratuaren bi orriak eta lotutako segurtasun-eranskina batera sinatuko dira. Alderdien identifikazioa eta benetako kokapena bete gabe badaude, ez da datu pertsonalik eskuratzeko baimenik sortzen.
''')

add('6.10 Datu pertsonalen tratamendu-enkargua', '''
Kontratu-eranskina - B eredua - Sinatu gabe - 2/2
## 6.10.2 Laguntza, azpikontratazioa eta amaiera
4. Azpieragileak. Hasieran ez dago azpieragilerik baimenduta. Hosting, euskarri edo beste hornitzaile batek datuetara sarbidea izan behar badu, arduradunaren aurretiazko idatzizko baimen espezifikoa lortuko da, eta datu-babeseko betebehar baliokideak ezarriko zaizkio. Eragileak azpieragilearen betebeharren erantzukizuna mantenduko du arduradunaren aurrean. Sarbiderik ez duen software-osagai baten egilea ez da horregatik azpieragilea.
5. Transferentziak. Ez da EEEtik kanpoko biltegiratze edo urruneko sarbiderik egingo arduradunaren jarraibide idatzirik eta GDPRren V. kapituluko mekanismo egokirik gabe. Zerbitzariaren kokapena bakarrik ez da nahikoa: euskarriaren kokapena eta sarbideak ere aztertuko dira.
6. Eskubideen eskaerak. Eragileak arduradunari lagunduko dio sarbide, zuzenketa, ezabaketa, aurkaratze, mugatze eta eramangarritasun eskaeretan, dagokion neurrian. Jasotako eskaera bi lanegunetan helaraziko dio, eta ez du arduradunaren izenean erantzungo berariazko baimenik gabe. Barne-epe horrek ez du interesdunari erantzuteko legezko epea ordezten.
7. Gorabeherak. Eragileak datu pertsonalen urraketa bidegabeko atzerapenik gabe jakinaraziko dio arduradunari, gehienez 24 ordutan jakin duenetik. Hasierako abisuak izaera, datu eta pertsona kategorien estimazioa, ondorio posibleak, hartutako neurriak eta kontaktua jasoko ditu, ahal den neurrian; informazio osagarria mailaka emango du. Ez du ikerketa bukatu arte itxarongo.
8. Arduradunari laguntzea. Eragileak segurtasun-betebeharrak, urraketen jakinarazpenak, eragin-ebaluazioak eta agintaritzari aurretiazko kontsultak betetzen lagunduko du, tratamenduaren izaera eta eskura duen informazioa kontuan hartuta. Agintaritzari edo interesdunei jakinarazteko erabakia arduradunari dagokio, legeak bestelakorik ezarri ezean.
9. Frogak eta auditoretza. Eragileak betetzea frogatzeko beharrezko informazioa emango du eta arduradunak edo hark baimendutako auditoreak egindako auditoretzak eta ikuskapenak ahalbidetu eta lagunduko ditu. Kontuen zerrenda, kontrolen frogak, gorabeherak eta ezabaketak dokumentatuko dira, beste bezero edo pertsonen datuak babestuta.
10. Amaiera. Arduradunak aukeratuta, datuak eta kopiak itzuli edo ezabatuko dira zerbitzua amaitzean, EBko edo estatu kideko lege batek gordetzea eskatzen duenean izan ezik. Legez gorde beharrekoa bereizita eta sarbide mugatuarekin mantenduko da, helburu horretarako soilik. Lan-kopiak 30 egunetan eta babeskopiak 30 eguneko txandan ezabatuko dira; ziurtagiria emango da.
11. Arduradunaren betebeharrak. Oinarri juridikoa, informazioa, datuen egokitasuna, jarraibideak eta eragilearen bermeak egiaztatuko ditu. Kontratu honek ez ditu interesdunen eskubideak edo GDPRren araberako erantzukizunak mugatzen.
Lekua/data: [________]. Arduradunaren sinadura: [________]. Eragilearen sinadura eta ordezkaritza: [________]. Gorabeheretarako kontaktuak: [________].
''')

add('6.11 CNC Guard: zerbitzu-kontratua eta lizentzia', '''
Kontratu-eranskina - C eredua - Sinatu gabe - 1/2
## 6.11.1 Alderdiak, entrega eta baimendutako erabilerak
Hornitzailea eta lizentzia-emailea: Jefrys [izen juridikoa, IFZ, helbidea eta ordezkaria]. Bezeroa eta lizentzia-hartzailea: ARAKAIN Makineriak [izen juridikoa, IFZ, helbidea eta ordezkaria].
1. Objektua eta bertsioa. Jefrysek CNC Guard [bertsioa/commit-a] garatu eta ARAKAINen zerbitzarian ezarriko du: datuen ingestioa, hiru ML ereduak, inferentzia-APIa eta hiru dashboard-ak. Kodea, models/cnc_failure_model.pkl, NiFi fluxuak, konfigurazio-txantiloiak eta dokumentazioa entregatuko ditu, hash-ekin eta hirugarrenen lizentziekin. Bezeroaren datuak eta pasahitzak ez dira pakete publikoan sartuko.
2. Prezioa eta ordainketa. Prezio osoa 6.000 euro da, BEZa aparte: garapena eta ezarpena, 4.500 euro; ordainpeko lizentzia, 1.500 euro. Entrega onartu ondoren faktura bakarra jaulkiko da eta 30 egunetan transferentziaz ordainduko da. Ez dago hileko kuotarik. Lizentzia ez-esklusiboa, mundu osorakoa eta epe mugagabekoa da, barne-erabilerarako; ez da eskubide guztien salmenta. Behin betiko lizentzia ordainketa osoarekin aktibatuko da; onarpen-probetarako aldi baterako erabilera baimentzen da.
3. Kopiak eta instalazioa. Enpresak kodea eta ereduak exekutatu, beharrezko lan-kopiak eta babeskopiak egin eta bere instalazioetan hedatu ahal izango ditu. Baimena enpresaren barne-erabilerarako da; ez du beste erakunde independenteentzako ustiapenik automatikoki barne hartzen.
4. Aldaketak. Enpresak bere beharretarako kodea, konfigurazioa, dashboard-ak, aldagaiak, atalaseak eta eredua aldatu edo berrentrenatu ahal izango ditu. Aldaketa bakoitzaren egilea, data eta bertsioa identifikatuko dira, eta jatorrizko egiletza-oharrak mantenduko dira. Jefrysen oniritzia ez da adieraziko hura lortu gabe.
5. Kanpoko mantentzea. Enpresak bere izenean lan egiten duen mantentze-hornitzaile bati kodea eskuratzeko aukera eman diezaioke, soilik lan horretarako, konfidentzialtasun-konpromisoarekin eta erabilera-muga berdinekin. Datu pertsonaletara sarbidea badago, dagokion tratamendu-enkargua eta azpieragileen baimenak aparte formalizatuko dira.
6. Berrentrenamendua eta segurtasuna. Enpresak erabiltzeko eskubidea duen datuekin soilik berrentrenatuko du. Ekoizpenean eredu edo atalase aldatu bat jarri aurretik, test independentea, akatsen eragina, datuen jatorria eta bertsiora itzultzeko aukera egiaztatuko ditu. Ez da lizentzia honen bidez segurtasun industrialeko erabilerarik automatikoki homologatzen.
Enpresaren datuetarako A eta B ereduek ezarritako mugak ez dira softwarea jasotzeagatik desagertzen. Era berean, datuak erabiltzeko baimenak ez du softwarearen eskubiderik ematen.
''')

add('6.11 CNC Guard: zerbitzu-kontratua eta lizentzia', '''
Kontratu-eranskina - C eredua - Sinatu gabe - 2/2
## 6.11.2 Mugak, eskubideak eta erantzukizunak
7. Banaketa eta merkataritza. Jefrysen kode propioa ezin da hirugarrenei saldu, publikoki banatu, azpilizentziatu edo kanpoko bezeroei zerbitzu gisa eskaini, Jefrysen aurretiazko idatzizko baimenik gabe. Enpresaren barne-erabilera komertziala bai baimentzen da. Klausula honek ez ditu hirugarrenen lizentziek edo legeak zuzenean aitortutako eskubideak murrizten.
8. Hirugarrenen osagaiak. Osagai bakoitzari bere lizentzia aplikatzen zaio. Entregaren inbentarioak izena, bertsioa, jatorria, lizentzia eta oharrak jasoko ditu. Lizentzia honek Jefrysen ekarpenei soilik eragiten die. Ez da baimenik ematen Docker, Elastic, MongoDB edo beste hornitzaileen markak eta produktuak Jefrysenak balira bezala erabiltzeko. Bezeroaren datuak ez daude lizentzia publiko baten pean; erabilera 6.9 akordioak mugatzen du.
9. Aldaketen eskubideak. Jatorrizko kodearen eskubideak jatorrizko titularrenak dira. Enpresak sortutako ekarpen berrien eskubideak aplikagarri den legearen eta benetako egiletza-harremanaren arabera zehaztuko dira, jatorrizko kodearen eskubideei kalterik egin gabe. Enpresak ez du aldaketa horiek Jefrysi lagatzeko betebeharrik; Jefrysek ez du haiek edo enpresaren datuak berrerabiltzeko baimen automatikorik.
10. Erabilera aurreikusia. CNC Guard ARAKAINen mantentze-lanetarako laguntza-sistema da. Ez du bermatzen matxura guztiak detektatzea, ezta matxuraren unea aurreikustea ere. Ez da langileen ebaluaziorako, erabaki diziplinarioetarako edo pertsonen segurtasunaren kontrol autonomorako erabiliko. Enpresako profesionalak alertak egiaztatu eta esku-hartzeak erabakiko ditu.
11. Onarpena eta bermea. ARAKAINek 10 lanegun izango ditu entrega probatu eta adostutako baldintzen ez-betetzeak idatziz azaltzeko. Jefrysek akatsak zuzendu eta onarpen-akta sinatuko da. Prezioak 90 eguneko akats-zuzenketa barne hartzen du onarpenetik, entregatutako bertsioak adostutakoa bete dezan. Ez du funtzio berririk edo etengabeko mantentzerik barne hartzen. Horiek aparte kontratatuko dira; ez dira baztertzen legez baztertu ezin diren erantzukizunak.
12. Ez-betetzea eta amaiera. Funtsezko ez-betetzea idatziz jakinaraziko da eta 30 egun emango dira zuzentzeko, kalteak berehala etetea beharrezkoa den kasuetan izan ezik. Ez-betetzea zuzentzen ez bada, lizentzia amaitu ahal izango da. Enpresak Jefrysen kodearen erabilera eta banaketa etengo ditu; legez gorde beharreko frogak bakarrik mantenduko ditu, sarbide mugatuarekin. Hirugarrenen eskubide independenteak mantenduko dira.
13. Legea eta gatazkak. Espainiako lege aplikagarria hartuko da erreferentzia. Lehenik idatzizko negoziazioa egingo da; gatazkak legez eskudun den organoari aurkeztuko zaizkio, derrigorrezko eskumen-arauak errespetatuta.
Lekua/data: [________]. Enpresaren ordezkaria: [________]. Jefrysen ordezkariaren sinadura: [________]. Entrega-manifestuaren erreferentzia: [________].
''')

add('6.12 Pribatutasun-informazioaren eredua', '''
Kontratu-eranskina - D eredua - Kontuak aktibatu aurretik osatzeko
Testu hau erabiltzaile-kontuak eta sarbide-logak kudeatzeko informazio-eredua da. Ez da langileen telemetria-profilaketarako baimena. Enpresak eremuak eta oinarri juridikoaren azterketa osatu behar ditu benetan erabiltzeko.
## 6.12.1 Erabiltzaileari emango zaion informazioa
Arduraduna: ARAKAIN Makineriak [izen juridikoa, IFZ eta helbidea]. Datu-babesari buruzko kontaktua: [helbidea]. Datuak babesteko ordezkaria, izendatuta badago: [kontaktua].
Helburuak: CNC Guard-era baimendutako sarbidea kudeatzea, segurtasun-gertaerak detektatzea eta gorabehera teknikoak aztertzea. Ez dira datuak langileen produktibitate-rankingak egiteko edo erabaki diziplinario automatizatuetarako erabiliko.
Datuak eta jatorria: laneko erabiltzaile-identifikatzailea, beharrezko kontaktua, IP helbidea, sarbidearen data/ordua eta segurtasun-gertaerak. Datuak erabiltzaileak emandako informaziotik, enpresak baimendutako kontu-zerrendatik eta erabilerak sortutako logetatik etorriko dira. Ez da pasahitzik testu arruntean gordeko.
Oinarri juridikoa: informazio-sistemaren segurtasunerako interes legitimoa, GDPRren 6.1.f artikulua, enpresak aurretiaz dokumentatutako beharrezkotasun- eta haztapen-azterketa aldekoa bada. Beste oinarri bat erabiltzen bada, zehaztu eta justifikatu beharko da. Ez da erabiltzailearen onarpena kontratu edo lan-harreman osorako baimen orokor bihurtuko.
Hartzaileak: enpresako baimendutako administratzaileak eta, beharrezkoa denean, kontratu bidez lotutako tratamendu-eragileak. Legezko betebehar bat dagoenean agintaritza eskudunei eman ahal izango zaie informazioa. Ez da datuen salmentarik edo publizitate-erabilerarik aurreikusten.
Transferentziak eta epeak: ez da EEEtik kanpoko transferentziarik aurreikusten. Sarbide-logak 90 egunetan ezabatuko dira, gorabehera baten frogak behar bezala justifikatuta bereizten direnean izan ezik. Kontuak baimena amaitzean desgaituko dira; kopien ezabaketa eta babeskopien txandaketa 6.6 atalean jasotzen dira.
Eskubideak: datuetara sartzea, zuzentzea, ezabatzea, tratamendua mugatzea eta aurka egitea eska dezakezu; eramangarritasuna legeko baldintzak betetzen direnean. Interes legitimoan oinarritutako tratamenduaren aurka egiteko aukera duzu, zure egoera partikularragatik. Eskaera [kontaktua] helbidera bidali, beharrezkoa den identifikazioarekin. Oro har hilabeteko epean erantzungo da; konplexutasunaren edo eskaera-kopuruaren ondorioz bi hilabetez luzatuz gero, lehen hilabetean jakinaraziko da.
Erreklamazioa aurkez dezakezu kontrol-agintaritza eskudunaren aurrean; enpresa pribatuaren esparru honetan AEPDren aurrean. Ez da aurreikusten pertsonengan ondorio esanguratsuak dituzten erabaki guztiz automatizaturik. Kontua erabiltzeko ezinbesteko datuak ez emateak sarbidea ez aktibatzea ekar dezake.
Informazioa eman den bertsioa eta data erregistratuko dira. Irakurri izanaren egiaztapena ez da baimen juridikoaren ordezkoa.
''')

add('6.13 Kontrolerako eta amaierarako erregistroak', '''
Eredu hauek erabakiak eta egiaztapenak dokumentatzeko erabiliko dira. Eremuak hutsik uzten dira; ez da oraindik egin gabeko kontrolik gainditutzat ematen.
## 6.13.1 Tratamenduaren fitxa eta baimenen erregistroa
| Eremua | Bete beharreko informazioa |
| Arduraduna / eragilea / kontaktuak | [Izen juridikoak, ordezkariak eta kontaktuak] |
| Helburua eta oinarri juridikoa | [Mantentzea / sarbideen segurtasuna; haztapena erantsita] |
| Pertsona- eta datu-kategoriak | [Kontuak, logak; telemetriaren identifikagarritasuna aztertuta] |
| Hartzaileak eta kokapena | [Baimendutako pertsonak; zerbitzaria; azpieragileak; transferentziak] |
| Iraupena eta segurtasuna | [6.6ko epeak; 6.5eko neurriak eta kontrolen frogak] |
| Jarraibideak eta sinatutako akordioak | [A/B/C erreferentziak, bertsioak eta datak] |
GDPRren 30. artikuluko jarduera-erregistroaren beharra eta salbuespenak aztertuko dira. Eragileak bere kontura egindako tratamendu-kategorien erregistroa ere prestatuko du, aplikagarria denean. Fitxa honek ez du erregistro osoa ordezten, eremu gehigarriak behar badira.
## 6.13.2 Entrega- eta onarpen-akta
Proiektua/bertsioa: [________]. Data: [________]. Kodearen commit-a eta fitxategien hash-ak: [________]. Entregatutako eredua, fluxuak, dashboard-ak eta dokumentazioa: [________]. Hirugarrenen lizentzien inbentarioa eta datuen atribuzioa: [________].
Probak: [autentifikazioa / baimenak / TLS / sarrera okerrak / babeskopia leheneratzea]. Kontrol bakoitzaren emaitza, arduraduna, data eta ebidentzia: [________]. Egiteke dauden neurriak eta produkziorako mugak: [________]. ARAKAINen eta Jefrysen ordezkarien sinadurak: [________]. Onarpenak ez du segurtasun industrialeko ziurtagiririk sortzen.
## 6.13.3 Gorabehera-fitxa eta ezabaketa-ziurtagiria
Gorabehera: [ID, detekzioaren eta ezagutzaren ordua, eragina, datu-kategoriak, neurriak, kontaktuak]. Jakinarazpenen orduak eta jakinarazi/ez jakinarazteko arrazoia: [________]. Leheneratzea eta prebentziozko ekintzak: [________].
Amaiera/ezabaketa: [zerbitzua eta amaiera-data]. Itzulitako datuak eta formatua: [________]. Ezabatutako CSVak, Kafka mezuak, NiFi datuak, indizeak, MongoDB datuak, notebook irteerak eta kopiak: [________]. Babeskopien azken ezabaketa-data: [________]. Legez gordetako salbuespenak eta arrazoia: [________]. Kredentzialen baliogabetzea: [________]. Egiaztatu duen pertsona eta enpresaren harrera: [________].
''')

add('6.14 Erreferentziak eta azken egiaztapena', '''
## 6.14.1 Erreferentzia nagusiak
Erreferentzien kontsulta-data: 2026/11/09. Irakaskuntzako materiala proiektuari aplikatu zaio, eta arau ofizialak erabili dira baldintzak zehazteko. Kontratu-eranskinek ARAKAIN bezeroaren eta Jefrys hornitzailearen arteko harremana, zerbitzuaren prezioa eta erabilera-baldintzak jasotzen dituzte.
@@ [1] GDPR: 2016/679 (EB) Erregelamendua. Bereziki 4-6, 12-22, 25, 28, 30 eta 32-36 artikuluak. BOEko testua: https://www.boe.es/buscar/doc.php?id=DOUE-L-2016-80807
@@ [2] AI Act: 2024/1689 (EB) Erregelamendua, testu bateratua. Bereziki 2, 3 eta 6 artikuluak, I/III eranskinak eta aplikazio-epeak: https://eur-lex.europa.eu/eli/reg/2024/1689/2026-07-27/eng
@@ [3] Europako Batzordea, AI Act aplikazio-egutegia eta AI Omnibus eguneraketa: https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai
@@ [4] AEPD, arduradunaren eta eragilearen arteko harremana eta kontratua: https://www.aepd.es/preguntas-frecuentes/2-tus-obligaciones-como-responsable-del-tratamiento/8-responsable-y-encargado-del-tratamiento
@@ [5] AEPD, datu pertsonalen urraketen jakinarazpena: https://www.aepd.es/derechos-y-deberes/cumple-tus-deberes/medidas-de-cumplimiento/brechas-de-datos-personales-notificacion
@@ [6] Espainiako 3/2018 Lege Organikoa, datu-babesa eta eskubide digitalak: https://www.boe.es/buscar/act.php?id=BOE-A-2018-16673
@@ [7] Jabetza Intelektualaren Legearen testu bategina, 1/1996 Legegintzako Errege Dekretua; softwareari buruzko 95-104 artikuluak: https://www.boe.es/buscar/act.php?id=BOE-A-1996-8930
@@ [8] Proiektuko datuen jatorria: ARAKAIN Makineriak enpresaren CNC makinen telemetria eta matxuren historikoa. Jefrysen erabilera-baimena 6.9 akordioan jasotzen da; datuak ez dira publikoki banatzen.
@@ [9] Emandako material didaktikoa: E1-Ereduak-Etika_eta_legea.pdf, Etika, araudia eta segurtasuna, 5071/RA6, Andoni Elola eta Jon Urteaga, 2025/2026. GDPR, AI Act, alborapenak, giza gainbegiraketa eta security/privacy by design.
## 6.14.2 Produkziora igaro aurretik
Enpresak eta Jefrysek datu errealen baimena eta identifikagarritasuna egiaztatuko dituzte, A eta C ereduak sinatuko dituzte eta B eredua aktibatuko dute behar denean. Pribatutasun-informazioa osatuko da, segurtasun-proben frogak erantsiko dira eta datuen kontserbazioa konfiguratuko da.
Azkenik, erabilera aurreikusia eta AI Act sailkapena berrikusiko dira. ARAKAINek eta Jefrysek entrega- eta onarpen-akta sinatuko dute. Sinatutako akordioek, probek eta egiaztatutako kontrolek osatuko dute zerbitzua ekoizpenean erabiltzeko dokumentazioa; txostenak bakarrik ez du adostasun-ziurtagiririk ordezten.
''')

def para(text,kind='body'):
    t=escape(text)
    # Auto-link references while allowing line wrapping.
    if kind=='small':
        t=re.sub(r'(https?://[^ ;]+)',lambda m:'<link href="'+m[1]+'" color="black">'+m[1]+'</link>',t)
    return Paragraph(t,styles[kind])

def flow(body):
    lines=body.splitlines(); out=[]; i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line: i+=1; continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                rows.append([para(c,'cell') for c in cells]); i+=1
            n=len(rows[0]); widths=([150,W-144-150] if n==2 else [122,205,W-144-327])
            table=Table(rows,colWidths=widths,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eeeeee')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5.5),('RIGHTPADDING',(0,0),(-1,-1),5.5),('TOPPADDING',(0,0),(-1,-1),5.5),('BOTTOMPADDING',(0,0),(-1,-1),5.5),('LINEBELOW',(0,0),(-1,0),.4,colors.grey),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#dddddd'))]))
            out.extend([table,Spacer(1,12)]); continue
        if line.startswith('## '):out.append(para(line[3:],'h'))
        elif line.startswith('@@ '):out.append(para(line[3:],'small'))
        else:out.append(para(line))
        i+=1
    return out

def footer(c,d):
    c.setFont('Arial',11); c.drawRightString(W-72,40,str(43+d.page))

story=[]
for idx,(title,body) in enumerate(pages):
    story.append(para(title,'title')); story.extend(flow(body))
    if idx<len(pages)-1:story.append(PageBreak())
section=TMP/'section.pdf'
SimpleDocTemplate(str(section),pagesize=(W,H),leftMargin=72,rightMargin=72,topMargin=64,bottomMargin=62).build(story,onFirstPage=footer,onLaterPages=footer)
sr=PdfReader(section)
if len(sr.pages)!=len(pages):
    for i,p in enumerate(sr.pages):print(i+44,(p.extract_text() or '')[:90].replace('\n',' '))
    raise RuntimeError(f'Overflow: {len(sr.pages)} instead of {len(pages)}')

# Rebuild the two existing contents pages with the original levels, plus chapter 6.
toc=[
('Sarrera',5),('1. Docker bidezko lan-ingurunea',6),('1.1 Docker eta Docker Compose',6),('1.2 Erabilitako zerbitzuak',6),('1.3 Datuen biltegiratzea',7),('1.4 Talde-lana',7),
('2. SMB, Filebeat eta Kafka',8),('2.1 Sarrera',8),('2.2 Sareko karpeta partekatua (SMB)',8),('2.3 Docker bidez karpetara sartzea',9),('2.4 Filebeat-en konfigurazioa',10),('2.5 Apache Kafka',12),('2.6 Funtzionamenduaren egiaztapena',13),('2.7 Datuen etengabeko jasotzea',14),('2.8 Segurtasuna eta kontuan hartu beharrekoak',15),
('3. Apache NiFi fluxuaren arkitektura',16),('3.1 Sarrera',16),('3.2 Fluxu nagusia',16),('3.3 Erroreen kudeaketa',21),('3.4 Datuen biltegiratzea',23),('3.5 Erabilitako prozesadore nagusiak',24),
('4. Machine Learning eredua eta FastAPI',25),('4.1 Sarrera',25),('4.2 Entrenamendurako datuak',25),('4.3 Datuak prestatzea',27),('4.4 Erabilitako Machine Learning ereduak',28),('4.5 Ereduen ebaluazioa',29),('4.6 Eredua gordetzea',31),('4.7 FastAPI zerbitzua',32),('4.8 Entrenamenduaren txostenak',34),('4.9 Ereduaren mugak',35),
('5. Elasticsearch eta Kibana',36),('5.1 Sarrera',36),('5.2 Elasticsearch eta Kibana',36),('5.3 CNC - Makinen Monitorizazioa',36),('5.4 CNC - Iragarpenak eta Alertak',38),('5.5 CNC - Ereduaren Ebaluazioa eta Kostuak',39),('5.6 Dashboard-en eguneraketa',43),
]
newtoc=[('6. Segurtasuna, etika eta lege-betetzea',44)]
seen=set()
for i,(title,body) in enumerate(pages):
    if i==0: newtoc.append(('6.1 Sarrera eta datuen erabilerari buruzko erabakia',44))
    elif title not in seen: newtoc.append((title,44+i))
    seen.add(title)
conclusion_start=44+len(pages)
newtoc += [('7. Ondorioak eta etorkizuneko hobekuntzak',conclusion_start),('7.1 Ondorio orokorrak',conclusion_start),('7.2 Lortutako emaitzak',conclusion_start),('7.3 Mugak eta etorkizuneko hobekuntzak',conclusion_start+1),('7.4 Azken hausnarketa',conclusion_start+1)]
def make_toc():
    b=BytesIO();c=canvas.Canvas(b,pagesize=(W,H))
    for num,entries in [(3,toc[:31]),(4,toc[31:]+newtoc)]:
        c.setFont('Arial',18);c.drawString(72,H-86,'Aurkibidea' if num==3 else 'Aurkibidea (jarraipena)')
        y=H-120
        for title,p in entries:
            main=bool(re.match(r'^\d+\. ',title)) or title=='Sarrera'
            c.setFont('Arial-Bold' if main else 'Arial',10.3)
            if main:y-=4
            c.drawString(72 if main else 84,y,title)
            c.drawRightString(W-72,y,str(p)); y-=18
        if y<65:raise RuntimeError('TOC overflow')
        c.setFont('Arial',11);c.drawRightString(W-72,40,str(num));c.showPage()
    c.save();return PdfReader(b)
tr=make_toc()

# Recreate only the conclusion pages to update chapter and page numbering.
orig=json.loads((TMP/'pages.json').read_text(encoding='utf-8'))
conclusion=TMP/'conclusion.pdf'
cs=[]
for k in [43,44]:
    t=orig[k]['text']; lines=t.splitlines(); blocks=[]; current=[]
    # pypdf preserves some line-breaking as single-word lines: normalise whitespace.
    t=re.sub(r'\s+',' ',t).strip()
    t=t.replace('simulagailuak sortutako CSV fitxategiak','ARAKAINen CNC makinek sortutako CSV fitxategiak')
    t=re.sub(r'\s+(44|45)$','',t)
    marks=list(re.finditer(r'6\. (?:Ondorioak eta etorkizuneko hobekuntzak)|6\.[1-4] (?:Ondorio orokorrak|Lortutako emaitzak|Mugak eta etorkizuneko hobekuntzak|Azken hausnarketa)',t))
    for j,m in enumerate(marks):
        title=m.group().replace('6.','7.',1)
        content=t[m.end():marks[j+1].start() if j+1<len(marks) else len(t)].strip()
        cs.append(para(title,'title' if title.startswith('7. ') else 'h'))
        if content:
            # Retain the original document's short explanatory paragraphs.
            chunks=re.split(r'(?=Proiektuaren hasieran,|Ondoren, Filebeat|Datu horiek Machine|FastAPI erabiliz,|Azkenik, Elasticsearch|Horrela, proiektuaren|Alde batetik,|Bestetik,|Eredu nagusiaren entrenamenduan,|Emaitza horrek|Gainera, iragarpenen|Kibanan sortutako|Proiektuan ez da Machine|Gainera, Docker|Orokorrean,|CNC Guard etorkizunean)',content)
            for chunk in chunks:
                if chunk.strip():
                    cs.append(Paragraph(escape(chunk.strip()),ParagraphStyle('original',parent=styles['body'],fontSize=11,leading=14.7,spaceAfter=12)))
    if k==43:cs.append(PageBreak())
def cf(c,d):c.setFont('Arial',11);c.drawRightString(W-72,40,str(conclusion_start+d.page-1))
SimpleDocTemplate(str(conclusion),pagesize=(W,H),leftMargin=72,rightMargin=72,topMargin=64,bottomMargin=62).build(cs,onFirstPage=cf,onLaterPages=cf)
cr=PdfReader(conclusion)
assert len(cr.pages)==2
w=PdfWriter()
for i in range(43):w.add_page(tr.pages[i-2] if i in [2,3] else r.pages[i])
for p in sr.pages:w.add_page(p)
for p in cr.pages:w.add_page(p)
w.add_metadata({'/Title':'CNC Guard - Dokumentazioa - Jefrys','/Author':'Jefrys','/Subject':'ARAKAIN eta Jefrys - Segurtasuna, lege-betetzea eta zerbitzu-kontratuak'})
w.add_outline_item('6. Segurtasuna, etika eta lege-betetzea',43)
for i,(title,_) in enumerate(pages):w.add_outline_item(title,43+i)
w.add_outline_item('7. Ondorioak eta etorkizuneko hobekuntzak',conclusion_start-1)
with OUT.open('wb') as f:w.write(f)
(TMP/'section_text.txt').write_text('\n\n'.join(a+'\n'+b for a,b in pages),encoding='utf-8')
print(json.dumps({'output':str(OUT),'pages':len(w.pages),'section_pages':len(sr.pages),'conclusions':conclusion_start},ensure_ascii=True))

