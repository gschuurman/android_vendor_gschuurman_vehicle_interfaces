// out: rev0.4/gnss/WIZARD.html
// Bring-up wizard data. Rebuild the page with: python3 PCB/wizard/build.py
const BOARD = {
  title: 'GPS-module rev 0.4',
  key: 'gnss-rev04',
  meta: `Ontwerp: <code>PCB/rev0.4/gnss/carradio_gnss_rev04.kicad_pcb</code> (gebruikt in de rev 0.6-set). Header J28 zit aan de onderkant. Pin 1 is het vierkante pad.`,
  tabs: [
  {id:'gps', name:"Multimeter (zonder voeding)", next:"Ga door met \"Eerste keer voeden\", met stroombegrenzing.", steps:[
 {t:"Voorbereiding",info:true,body:`
  <p>Module los, geen antenne, niets aangesloten. Header J28 zit aan de <b>onderkant</b>; pin 1 is het <b>vierkante</b> pad.</p>
  <p>Multimeter op <b>Ω</b>, pennen tegen elkaar: bijna 0 Ω.</p>
  <div class="note">GND-pinnen: 3, 6, 11, 12 en 16. Deze wizard gebruikt pin 3.</div>`},
 {t:"GND controleren",setting:"piepstand",red:"J28 pin 3",black:"J28 pin 6",exp:"≈ 0 Ω (piept)",small:"",
  fail:"Pin 3 of 6 slecht gesoldeerd."},
 {t:"3,3 V naar GND",setting:"Ω",red:"J28 pin 1 (+3V3_GNSS)",black:"J28 pin 3",exp:"loopt op → hoger dan ~1 kΩ",small:"C14 10 µF laadt",
  fail:"Onder 100 Ω: kortsluiting. Kijk naar C14, C15 en de VCC-pads van de NEO-M9N (pin 23 en 7)."},
 {t:"Pin 1 en 2 samen",setting:"piepstand",red:"J28 pin 1",black:"J28 pin 2",exp:"≈ 0 Ω (piept)",small:"",
  fail:"Pin 1 of 2 slecht gesoldeerd."},
 {t:"Backup-voeding",setting:"Ω",red:"J28 pin 4 (V_BCKP)",black:"J28 pin 3",exp:"hoger dan ~1 kΩ",small:"",
  fail:"Kortsluiting bij C16 of NEO-M9N pin 22."},
 {t:"Antenne-voeding",setting:"Ω (200 Ω-bereik)",red:"middenpin van J11 (U.FL)",black:"pad van C17 dat níet GND is",exp:"≈ 10 Ω",small:"L2 + R41 in serie",
  pre:"C17 is de 10 nF bij R41. Trek de stand van je meetpennen (stap Voorbereiding) ervan af.",
  fail:"Open: L2 (0402, klein) of R41 slecht gesoldeerd. Veel lager dan 10 Ω: R41 overbrugd."},
 {t:"Antenne niet aan GND",setting:"Ω",red:"middenpin van J11",black:"buitenkant (mantel) van J11",exp:"niet 0 Ω",small:"zelfde orde als stap 3",
  fail:"0 Ω: het middenpad van de U.FL raakt de mantel. Opnieuw solderen."},
 {t:"USB-datalijnen",setting:"Ω",red:"J28 pin 7 (D+)",black:"J28 pin 9 (D-)",exp:"hoog / OL",small:"ook elk naar pin 3: geen 0 Ω",
  fail:"Brug tussen D+ en D-: kijk bij R102/R103 en NEO-M9N pin 5 en 6."},
 {t:"UART-lijnen",setting:"Ω",red:"J28 pin 8 (TXD)",black:"J28 pin 10 (RXD)",exp:"hoog / OL",small:"ook elk naar pin 3: geen 0 Ω",
  fail:"Brug bij NEO-M9N pin 20 en 21."},
 {t:"Reset, safeboot, PPS",setting:"Ω",red:"J28 pin 13, 15 en 14 om de beurt",black:"J28 pin 3",exp:"niet 0 Ω",small:"interne pull-ups mogen tientallen kΩ geven",
  fail:"0 Ω op pin 13: de module staat dan altijd in reset. Kijk bij NEO-M9N pin 8, 1 en 3."},
]},
  {id:'gpsp', name:"Eerste keer voeden", next:"Daarna gaat de module op J27 van het main board: wizard main board, \"Modules erop\".", steps:[
 {t:"Aansluiten",info:true,body:`
  <p>Doe dit pas als alle multimetermetingen van de GPS-module kloppen. Nog geen antenne.</p>
  <p>Labvoeding <b>uit</b>. Stel in op <b>3,3 V</b> (meet het eerst na: nooit boven 3,6 V) en een stroomgrens van <b>100 mA</b>. Plus op <b>J28 pin 1</b>, min op <b>J28 pin 3</b>. Leg een draadje van <b>pin 4</b> naar <b>pin 2</b> (backup-voeding aan VCC).</p>
  <p>Met een Bus Pirate 5 kan het ook: voeding <code>W 3.3 100</code> (3,3 V, 100 mA grens) op J28 pin 1, GND op pin 3, en de UART-bridge op 38400 baud.</p>
  <div class="note">Nooit 5 V op welke pin dan ook, ook niet de rode draad van een USB-kabel.</div>`},
 {t:"Inschakelen",setting:"display van de labvoeding",exp:"≈ 20 – 45 mA",small:"de module zoekt satellieten",
  fail:"Op de stroomgrens: meteen uit en melden. 0 mA: kijk naar pin 1 en de VCC-pads van de NEO-M9N."},
 {t:"Niet in reset",setting:"V DC",red:"J28 pin 13 (RESET)",black:"J28 pin 3",exp:"≈ 3,3 V",small:"",
  fail:"Laag: de module staat in reset. Kijk naar NEO-M9N pin 8."},
 {t:"Antennevoeding",setting:"V DC",red:"pad van C17 dat níet GND is",black:"J28 pin 3",exp:"≈ 3,0 – 3,3 V",small:"VCC_RF voor de actieve antenne",
  fail:"0 V: kijk naar NEO-M9N pin 9."},
 {t:"UART aansluiten",info:true,body:`
  <p>Gebruik een USB-serieel adapter op <b>3,3 V</b>-niveau. Sluit de 3V3- of 5V-pin van de adapter <b>niet</b> aan.</p>
  <dl class="row"><dt>RX van adapter</dt><dd>J28 pin 8 (TXD)</dd><dt>TX van adapter</dt><dd>J28 pin 10 (RXD)</dd><dt>GND</dt><dd>J28 pin 6</dd></dl>
  <p>Open een terminal (PuTTY, Arduino Serial Monitor) op <b>38400 8N1</b>.</p>`},
 {t:"NMEA-tekst",setting:"terminal 38400 8N1",exp:"$GNRMC, $GNGGA … elke seconde",small:"zonder fix met lege velden",
  fail:"Onleesbare tekens: probeer 9600. Helemaal niets: RX en TX omgewisseld, of pin 8 niet goed gesoldeerd."},
 {t:"Antenne aansluiten",setting:"display van de labvoeding",exp:"stroom stijgt ~5 – 20 mA",small:"actieve antenne, via U.FL-naar-SMA pigtail",
  pre:"Klik de U.FL recht op J11, zonder te kantelen.",
  fail:"Stroom naar de grens: antenne met DC-kortsluiting (passief) of kortsluiting in de pigtail. Antenne los en melden."},
 {t:"USB",setting:"Apparaatbeheer (Windows)",exp:"COM-poort van u-blox",small:"VID 1546",
  pre:"Tweede doorgeknipte USB-kabel: groen (D+) op pin 7, wit (D-) op pin 9, zwart op pin 11. Rood NIET aansluiten, isoleer hem. De UART mag aan blijven.",
  fail:"Niets: controleer D+ en D-, en R102/R103 (27 Ω)."},
 {t:"Fix",setting:"u-center of u-center 2",exp:"positie binnen ~30 s – enkele min",small:"satellieten rond 35 – 45 dBHz",
  pre:"Antenne buiten of tegen het raam met vrij zicht op de lucht.",
  fail:"Satellieten zichtbaar maar zwak (onder 25 dBHz): antenne verplaatsen, pigtail controleren. Geen satellieten: meet de antennevoeding opnieuw met antenne erop."},
 {t:"PPS (optioneel)",setting:"LED met 1 kΩ naar GND, of scoop",red:"J28 pin 14",black:"J28 pin 3",exp:"1 puls per seconde na de fix",small:"",
  fail:"Geen puls met fix: kijk naar NEO-M9N pin 3."},
]},
  ],
};
