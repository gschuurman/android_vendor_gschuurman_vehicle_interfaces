// out: rev0.6/usb/WIZARD.html
// Bring-up wizard data. Rebuild the page with: python3 PCB/wizard/build.py
const BOARD = {
  title: 'USB-module rev 0.6',
  key: 'usb-rev06',
  meta: `Ontwerp: <code>PCB/rev0.6/usb/carradio_usb_rev06.kicad_pcb</code>. Header J26 zit aan de onderkant; de soldeerpunten meet je aan de bovenkant. Pin 1 is het vierkante pad.`,
  tabs: [
  {id:'usb', name:"Multimeter (zonder voeding)", next:"Ga door met \"Eerste keer voeden\", met stroombegrenzing.", steps:[
 {t:"Voorbereiding",info:true,body:`
  <p>Module los op tafel, niets aangesloten. Header J26 zit aan de <b>onderkant</b>; de soldeerpunten zie je aan de bovenkant. Pin 1 is het <b>vierkante</b> pad.</p>
  <p>Zet de multimeter op <b>Ω</b> (auto of 200 kΩ) en houd de pennen tegen elkaar: hij moet bijna 0 Ω geven. Onthoud die waarde, die trek je straks af.</p>
  <div class="note">Les van het eerste bord: het thermische pad onder <b>U15</b> (LMR33630) is AGND en moet echt gesoldeerd zijn. Op het eerste bord was het los: de buck negeerde zijn terugkoppeling en zette de ingangsspanning op de 5 V. Met de hand: pad eerst vlak vertinnen, dan U15 met hete lucht of op de hotplate.</div>
  <div class="note">Een meting die langzaam oploopt is normaal: de multimeter laadt dan een condensator op. Wacht steeds tot de waarde stilstaat of OL wordt.</div>`},
 {t:"GND controleren",setting:"Ω of piepstand",red:"J26 pin 3",black:"J26 pin 4",exp:"≈ 0 Ω (piept)",small:"beide zijn GND",
  fail:"Geen verbinding: pin 3 of 4 slecht gesoldeerd. Nasolderen en opnieuw meten. Gebruik vanaf nu pin 3 als GND-punt."},
 {t:"12 V-ingang naar GND",setting:"Ω",red:"J26 pin 1 (VSYS_IN)",black:"J26 pin 3 (GND)",exp:"loopt op → hoog / OL",small:"C64 10 µF laadt op",
  fail:"Onder 10 Ω is kortsluiting. Kijk naar C64, C65 en de pinnen 1–2 van U15 (LMR33630). Niet voeden voor dit opgelost is."},
 {t:"Pin 1 en 2 samen",setting:"piepstand",red:"J26 pin 1",black:"J26 pin 2",exp:"≈ 0 Ω (piept)",small:"beide VSYS_IN",
  fail:"Een van de twee pinnen is slecht gesoldeerd."},
 {t:"Enable-pin",setting:"Ω",red:"J26 pin 16 (EN)",black:"J26 pin 3",exp:"hoog / OL",small:"",
  fail:"Kortsluiting op EN: kijk bij U15 pin 3."},
 {t:"5 V-buckuitgang",setting:"Ω",red:"pad van C68 dat níet 0 Ω naar GND geeft",black:"J26 pin 3",exp:"≈ 100–124 kΩ",small:"vaste weg via R75+R76 = 124 kΩ; OL of MΩ is fout",
  pre:"C68 is een van de vier 22 µF-condensatoren naast spoel L4. Eén pad is GND (0 Ω), het andere is +5V_USB.",
  fail:"Onder 1 kΩ: kijk naar C68–C72 en U16 (TPS2561, pinnen 2–5). MΩ of OL: R75 (100 kΩ) of R76 (24 kΩ) niet goed gesoldeerd; meet ze los. Niet voeden: zonder deler kan de buck bijna 12 V op de USB-poorten zetten."},
 {t:"12 V niet aan 5 V",setting:"Ω",red:"J26 pin 1",black:"+5V_USB-pad van C68",exp:"hoog (kΩ of meer)",small:"",
  fail:"Lage weerstand tussen 12 V en 5 V betekent een brug bij U15. Zeker niet voeden: de 12 V zou op alles komen."},
 {t:"VBUS poort 1 (J19)",setting:"Ω",red:"pad van C73 dat níet GND is",black:"J26 pin 3",exp:"loopt op → hoog / OL",small:"C73 100 µF laadt, kan even duren",
  pre:"C73 is de 100 µF-condensator bij J19. Je mag ook pin 1 van J19 nemen (VBUS).",
  fail:"Onder 10 Ω: waarschijnlijk U17 (USBLC6) 180° gedraaid, of een brug bij U16 pin 9. Doe eerst de volgende stap."},
 {t:"U17 richting (diodetest)",setting:"diodestand",red:"J26 pin 3 (GND)",black:"VBUS-pad van C73",exp:"zakt naar ≈ 0,5–0,7 V",small:"diode in U17 geleidt van GND naar VBUS; pennen omgedraaid: OL",
  fail:"Blijft hij oplopen tot OL, dan zit U17 180° gedraaid. Pin 1 hoort linksboven (headerkant), pad 5 VBUS aan de kant van de USB-A-sockets. Eerst omdraaien, anders sluit hij VBUS kort zodra er spanning op komt."},
 {t:"VBUS poort 2 (J20)",setting:"Ω",red:"pad van C74 dat níet GND is",black:"J26 pin 3",exp:"loopt op → hoog / OL",small:"C74 100 µF",
  fail:"Onder 10 Ω: waarschijnlijk U18 gedraaid, of een brug bij U16 pin 8."},
 {t:"U18 richting (diodetest)",setting:"diodestand",red:"J26 pin 3 (GND)",black:"VBUS-pad van C74",exp:"zakt naar ≈ 0,5–0,7 V",small:"pennen omgedraaid: OL",
  fail:"Loopt op tot OL: U18 zit 180° gedraaid. Omdraaien voor je voedt."},
 {t:"5 V voor de hub",setting:"Ω",red:"J26 pin 5 (+5V_SYS)",black:"J26 pin 3",exp:"hoger dan ~1 kΩ",small:"CH334R en C75",
  fail:"Onder 100 Ω: kijk naar C75 en U14 pin 12."},
 {t:"Pin 5 en 6 samen",setting:"piepstand",red:"J26 pin 5",black:"J26 pin 6",exp:"≈ 0 Ω (piept)",small:"",
  fail:"Pin 5 of 6 slecht gesoldeerd."},
 {t:"SDR-poort via zekering",setting:"Ω",red:"J26 pin 5",black:"pin 1 van J17 (VBUS SDR)",exp:"< 1 Ω",small:"via PTC F5",
  fail:"Open: F5 slecht gesoldeerd of J17 pin 1 los."},
 {t:"Hub 3,3 V",setting:"Ω",red:"pad van C76 dat níet GND is",black:"J26 pin 3",exp:"hoger dan ~1 kΩ",small:"interne regelaar van de hub",
  fail:"Onder 100 Ω: kijk naar C76, C77 en U14 pinnen 9 en 13."},
 {t:"USB-datalijnen hub",setting:"Ω",red:"J26 pin 10 (D+)",black:"J26 pin 12 (D-)",exp:"hoog / OL",small:"ook elk van beide naar pin 3: geen 0 Ω",
  fail:"Een brug tussen D+ en D-: kijk bij U14 pinnen 10 en 11."},
 {t:"Status-signalen",setting:"Ω",red:"J26 pin 15, 17 en 18 om de beurt",black:"J26 pin 3",exp:"hoog / OL alle drie",small:"PG en FAULT1/2",
  fail:"Kortsluiting naar GND: kijk bij U15 pin 4 (PG) of U16 pinnen 6 en 10."},
]},
  {id:'usbp', name:"Eerste keer voeden", next:"Daarna gaat de module op het main board: zie de wizard van het main board, tabblad \"Modules erop\".", steps:[
 {t:"Aansluiten",info:true,body:`
  <p>Doe dit pas als alle multimetermetingen van de USB-module kloppen.</p>
  <p>Labvoeding <b>uit</b>. Stel in op <b>12,0 V</b> en een stroomgrens van <b>100 mA</b>. Plus op <b>J26 pin 1</b>, min op <b>J26 pin 3</b>. Leg een draadje van <b>pin 16</b> (EN) naar <b>pin 1</b>, zodat de buck aangaat. Nog niets in de USB-poorten.</p>
  <div class="note">Houd je vinger bij de aan/uit-knop. Loopt de stroom tegen de grens aan, of wordt iets warm: meteen uit.</div>`},
 {t:"Inschakelen",setting:"display van de labvoeding",exp:"minder dan ~20 mA",small:"spanning blijft 12,0 V",
  fail:"Staat hij op de stroomgrens (100 mA, spanning zakt): meteen uit. Voel welk onderdeel warm werd (U15, U16, L4) en meld het hier."},
 {t:"5 V van de buck",setting:"V DC",red:"pad van C68 dat níet GND is",black:"J26 pin 3",exp:"5,1 – 5,2 V",small:"berekend 5,17 V",
  fail:"Rond 12 V: meteen uit, de buck regelt niet. Meest waarschijnlijk is het thermische pad (AGND) van U15 niet gesoldeerd; daarna R75/R76 en U15 pin 5. 0 V: kijk of pin 16 echt aan pin 1 zit en naar U15 pin 3. Andere waarde: meld hem hier."},
 {t:"VBUS poort 1 (J19)",setting:"V DC",red:"pad van C73 dat níet GND is",black:"J26 pin 3",exp:"5,1 – 5,2 V",small:"U16 staat altijd aan",
  fail:"0 V: U16 (TPS2561) schakelt niet; kijk naar pinnen 2–5 en 9 en het exposed pad."},
 {t:"VBUS poort 2 (J20)",setting:"V DC",red:"pad van C74 dat níet GND is",black:"J26 pin 3",exp:"5,1 – 5,2 V",small:"",
  fail:"0 V: kijk naar U16 pin 8."},
 {t:"SDR-poort nog zonder spanning",setting:"V DC",red:"J26 pin 5",black:"J26 pin 3",exp:"0 V",small:"J17 en de hub krijgen 5 V via pin 5, nu nog niet aangesloten",
  fail:"Spanning op pin 5 betekent een verbinding tussen +5V_USB en +5V_SYS die er niet hoort te zijn. Uitzetten en melden."},
 {t:"Power-good (optioneel)",setting:"V DC",red:"J26 pin 15",black:"J26 pin 3",exp:"≈ 5 V",small:"eerst 10 kΩ van pin 15 naar het hete pad van C68",
  pre:"PG is open drain; de pull-up zit op het hoofdbord. Zet daarom tijdelijk een 10 kΩ-weerstand van pin 15 naar +5V_USB.",
  fail:"0 V met de weerstand erop: U15 meldt dat de uitgang niet goed is, of PG (U15 pin 4) zit tegen GND."},
 {t:"Belasting 0,5 A",setting:"V DC",red:"pad van C73 dat níet GND is",black:"J26 pin 3",exp:"boven 4,9 V",small:"labvoeding: ≈ 0,25 A bij 12 V",
  pre:"Zet de stroomgrens op 1 A. Belast J19 met 10 Ω (minstens 5 W) tussen VBUS en GND, of met een USB-load op 0,5 A.",
  fail:"Zakt de spanning ver weg of trekt de labvoeding veel meer dan 0,3 A: uitzetten en melden."},
 {t:"Stroombegrenzing (optioneel)",setting:"V DC",red:"J26 pin 18 (FAULT1)",black:"J26 pin 3",exp:"zakt naar ≈ 0 V",small:"met 10 kΩ van pin 18 naar +5V_USB; J20 blijft 5 V",
  pre:"Stroomgrens op 2 A. Belast J19 heel kort (enkele seconden) met 2,2 Ω, 5 W. U16 begrenst rond 1,4 A en de VBUS van J19 zakt. Daarna de belasting weghalen; alles herstelt. Hetzelfde kan op J20 met FAULT2 op pin 17.",
  fail:"Blijft FAULT hoog terwijl VBUS zakt, kijk naar U16 pin 10. Wordt de weerstand of U16 erg heet, korter belasten."},
 {t:"Hub aansluiten",info:true,body:`
  <p>Laat de 12 V aan. Neem een doorgeknipte USB-kabel naar de PC, het liefst via een USB-stroommeter.</p>
  <dl class="row"><dt>Rood (5 V)</dt><dd>J26 pin 5</dd><dt>Zwart (GND)</dt><dd>J26 pin 4</dd><dt>Groen (D+)</dt><dd>J26 pin 10</dd><dt>Wit (D-)</dt><dd>J26 pin 12</dd></dl>
  <div class="note">Houd de losse draadjes kort, onder 10 cm. Controleer de kleuren met de multimeter als de kabel geen standaardkleuren heeft.</div>`},
 {t:"Hub 3,3 V",setting:"V DC",red:"pad van C76 dat níet GND is",black:"J26 pin 3",exp:"≈ 3,3 V",small:"stroom uit de PC: enkele tientallen mA",
  fail:"0 V: kijk of pin 5 echt 5 V krijgt. Veel stroom uit de PC: meteen loskoppelen."},
 {t:"Hub op de PC",setting:"Apparaatbeheer (Windows)",exp:"nieuwe USB-hub",small:"WCH, VID 1A86",
  fail:"Niets of 'onbekend apparaat': controleer D+ en D- (niet omgewisseld), de kristal Y2 en U14 pinnen 10, 11, 15 en 16."},
 {t:"USB-stick in J19 en J20",setting:"Verkenner / USB Tree View",exp:"stick verschijnt, High Speed",small:"",
  fail:"Alleen Full Speed: meestal de losse draadjes. Helemaal niets: kijk naar de datapinnen van J19/J20 en U14 pinnen 5–8."},
 {t:"RTL-SDR in J17",setting:"Apparaatbeheer of SDR-programma",exp:"dongle verschijnt en werkt",small:"gevoed via F5 (0,5 A)",
  fail:"Geen spanning op J17: F5. Wel spanning maar niet gezien: U14 pinnen 3 en 4."},
]},
  {id:'usbf', name:"Storing: 12 V zakt in", next:"", steps:[
 {t:"Wat er aan de hand is",info:true,body:`
  <p>Met het draadje op pin 16 (EN) zakt de 12 V naar ongeveer 7 V. Je labvoeding zit dan op zijn stroomgrens: ongeveer 95 mA, 0,66 W. Zonder het draadje blijft het 12 V. De ingang is dus in orde, en de stroom gaat via de buck U15 naar de 5 V-kant.</p>
  <p>Zonder belasting hoort de module minder dan 20 mA te trekken. Ergens gaat dus ongeveer 0,6 W heen. Deze stappen zoeken uit waar.</p>
  <dl class="row"><dt>Labvoeding</dt><dd>12,0 V, stroomgrens 100 mA</dd><dt>Plus / min</dt><dd>J26 pin 1 / J26 pin 3</dd><dt>EN</dt><dd>draadje pin 16 naar pin 1</dd><dt>USB-poorten</dt><dd>leeg</dd></dl>
  <div class="note">Zet de voeding per meting maar een paar seconden aan en daarna weer uit. Met 100 mA stroomgrens gaat er niets kapot, maar langer aanlaten levert niets op.</div>`},
 {t:"Uitgangsspanning van de buck",setting:"V DC",red:"pad van C68 dat níet GND is",black:"J26 pin 3",exp:"5,1 – 5,2 V",small:"zegt of de buck zijn 5 V haalt",
  pre:"Dit is de belangrijkste meting. De buck maakt van de 12 V een 5 V op C68 tot en met C71. Als die 5 V klopt, werkt de buck en trekt iets áchter de buck de stroom. Is die 5 V te laag, dan haalt de buck hem niet.",
  fail:"Meld de waarde hier. Rond 5,2 V: de buck werkt, er hangt iets op de 5 V dat ruim 100 mA trekt; ga door met stap 3 en 4. Tussen 0,5 en 4,5 V: de 5 V wordt omlaag getrokken of de buck start niet goed op; ga naar stap 5. Bijna 0 V: kortsluiting op de 5 V of de buck schakelt niet. Boven 6 V: meteen uit, dan regelt de buck niet."},
 {t:"Poort 1 achter de schakelaar",setting:"V DC",red:"pad van C73 dat níet GND is",black:"J26 pin 3",exp:"zelfde als C68",small:"VBUS van J19, achter U16",
  pre:"U16 (TPS2561) schakelt de 5 V door naar de twee poorten en begrenst de stroom per poort. Is C73 veel lager dan C68, dan begrenst U16 op poort 1, omdat daar iets stroom trekt.",
  fail:"Veel lager dan C68: het zit op poort 1, bij C73, U17 of J19 (VBUS tegen GND of D+/D-). Kijk met de loep naar U17 en de pinnen van J19. Gelijk aan C68 maar allebei laag: ga door met stap 4."},
 {t:"Poort 2 achter de schakelaar",setting:"V DC",red:"pad van C74 dat níet GND is",black:"J26 pin 3",exp:"zelfde als C68",small:"VBUS van J20, achter U16",
  pre:"Hetzelfde voor poort 2.",
  fail:"Veel lager dan C68: het zit op poort 2, bij C74, U18 of J20."},
 {t:"Inschakelpiek of echte belasting?",setting:"display van de labvoeding",exp:"12 V, stroom zakt onder ~20 mA",small:"stroomgrens tijdelijk 300 mA, 2 seconden",
  pre:"Bij het aanzetten moet de buck in een paar milliseconden ongeveer 290 µF op de 5 V opladen. Dat kost even meer dan 100 mA. Sommige labvoedingen blijven daarna in de stroombegrenzing hangen. Zet de stroomgrens op 300 mA, zet aan en kijk 2 seconden. Daarna weer uit.",
  fail:"Blijft hij boven 100 mA of zakt de 12 V weer in, dan is het een echte belasting en geen inschakelpiek. Ga naar stap 6. Zakt hij wel naar onder 20 mA, dan was het alleen de piek. Test dan verder met de stroomgrens op 300 mA."},
 {t:"Warmte zoeken",setting:"vinger of druppel isopropylalcohol",exp:"het onderdeel dat warm wordt",small:"stroomgrens 300 mA, 5 seconden",
  pre:"Alleen als stap 5 een echte belasting liet zien. Bij 300 mA gaat er 1 tot 3 W in, en het onderdeel dat dat opneemt wordt binnen een paar seconden warm. Voel aan U15, L4, U16, U17, U18 en C68 tot C74. Een druppel alcohol verdampt zichtbaar sneller op een warm onderdeel.",
  fail:"Noteer welk onderdeel warm werd en meld het hier. Dat is bijna altijd de plek van de fout (een brug onder het onderdeel, een verkeerd gedraaid onderdeel of een defecte condensator)."},
 {t:"Bekende oorzaak: PowerPAD van U15",info:true,body:`
  <p>Op het eerste bord gaf deze storing: met EN aan stond C68 op de ingangsspanning, FB was 1,2 V maar werd genegeerd, en VCC (pin 6) was 5,87 V. Oorzaak: het thermische pad van U15 is <b>AGND</b> en was niet gesoldeerd. Pin 1 is alleen PGND.</p>
  <p>Oplossing: U15 eraf met hete lucht, beide pads vlak vertinnen, terugzetten. Daarna eerst testen op <b>6 V</b>, zodat de 5 V-kant nooit meer dan 6 V kan krijgen. Controleer daarna U17/U18 en C73/C74 opnieuw.</p>`},
]},
  ],
};
