// out: rev0.7/capture_1cam/WIZARD.html
// Bring-up wizard data. Rebuild the page with: python3 PCB/wizard/build.py
const BOARD = {
  title: 'Capturemodule rev 0.7 (1 camera)',
  key: 'capture1-rev07',
  meta: `Ontwerp: <code>PCB/rev0.7/capture_1cam/carradio_capture_rev07.kicad_pcb</code>. MS2107 CVBS-naar-USB (UVC). Pin 1 is het vierkante pad.`,
  tabs: [
  {id:'capm', name:"Multimeter (zonder voeding)", next:"Ga door met \"Eerste keer voeden\", met stroombegrenzing.", steps:[
 {t:"Voorbereiding",info:true,body:`
  <p>Module los, niets aangesloten. <b>J2</b> (2×3 pinheader) zit aan de <b>onderkant</b> en gaat in J29 op de USB-module: pin 1/2 +5V_CAP, 3 D+, 4 D-, 5/6 GND. Pin 1 is het vierkante pad.</p>
  <p>Kijk met de loep naar de 0,5 mm-pinnen van de MS2107 (U1) en of de stip bij pin 1 klopt, en naar de richting van de USBLC6 U2.</p>
  <p>De EEPROM U3 en R5 zit niet op het bord (DNP); dat is normaal.</p>
  <p>Multimeter op <b>Ω</b>, pennen tegen elkaar: bijna 0 Ω.</p>`},
 {t:"GND controleren",setting:"piepstand",red:"J2 pin 5",black:"J2 pin 6, daarna J1 pin 2",exp:"≈ 0 Ω (piept)",small:"",
  fail:"Geen piep: die pin is slecht gesoldeerd. Gebruik verder J2 pin 5 als GND."},
 {t:"5 V-ingang naar GND",setting:"Ω",red:"J2 pin 1 (+5V_CAP)",black:"J2 pin 5",exp:"loopt op → hoger dan ~1 kΩ",small:"C1 10 µF laadt op",
  fail:"Onder 100 Ω: kortsluiting. Kijk naar C1, C2, de richting van U2 (een gedraaide USBLC6 sluit de 5 V kort), en pin 16 van U1."+""},
 {t:"Pin 1 en 2 samen",setting:"piepstand",red:"J2 pin 1",black:"J2 pin 2",exp:"≈ 0 Ω (piept)",small:"",
  fail:"Pin 1 of 2 van J2 slecht gesoldeerd."},
 {t:"USB-datalijnen",setting:"Ω",red:"J2 pin 3 (D+)",black:"J2 pin 4 (D-)",exp:"hoog / OL",small:"ook elk naar pin 5: geen 0 Ω",
  fail:"Brug tussen D+ en D-: kijk bij U1 pin 32 en 33."},
 {t:"Camera 1: 3,3 V digitaal",setting:"Ω",red:"pad van C3 dat níet GND is",black:"J2 pin 5",exp:"loopt op → hoger dan ~1 kΩ",small:"interne 3,3 V-regelaar van U1 (pin 17)",
  fail:"Onder 100 Ω: brug bij de voedingspinnen van U1 (10, 14, 17, 20, 34, 46) of bij C3–C6."},
 {t:"Camera 1: ferriet FB1",setting:"Ω (200 Ω-bereik)",red:"pad van C3 dat níet GND is",black:"pad van C7 dat níet GND is",exp:"< 1 Ω",small:"3,3 V digitaal naar 3,3 V analoog",
  fail:"Open: FB1 slecht gesoldeerd. Dan krijgen de video-ADC en de USB-PHY geen voeding."},
 {t:"Camera 1: 1,2 V kern",setting:"Ω",red:"pad van C11 dat níet GND is",black:"J2 pin 5",exp:"hoger dan ~100 Ω",small:"interne 1,2 V-regelaar (pin 18)",
  fail:"Onder 10 Ω: brug bij pin 18, 24 of 48 van U1, of bij C11–C13."},
 {t:"Camera 1: video-afsluiting",setting:"Ω (200 Ω-bereik)",red:"J1 pin 1 (video)",black:"J1 pin 2 (GND)",exp:"≈ 75 Ω",small:"R2, de 75 Ω-afsluiting van de camerakabel",
  pre:"J1 is de witte 2-polige JST PH aan de rand. Pin 1 is het vierkante pad.",
  fail:"OL: R2 of J1 pin 1 los. 0 Ω: brug bij U2 (USBLC6) of J1. Pin 2 niet aan GND: J1 pin 2 los."},
 {t:"Camera 1: video naar de chip",setting:"Ω",red:"pad van C18 aan de kant van U1 (AVIN, pin 8)",black:"J2 pin 5",exp:"niet 0 Ω",small:"C18 47 nF koppelt de video naar pin 8",
  fail:"0 Ω: brug bij U1 pin 7–9."},
 {t:"Camera 1: REXT",setting:"Ω",red:"pad van R1 dat níet GND is",black:"J2 pin 5",exp:"≈ 4,7 kΩ (of iets lager)",small:"R1 4,7 kΩ 1 %, stelt de USB-stroom in",
  fail:"OL: R1 los. Een verkeerde REXT geeft een USB-apparaat dat niet of alleen op Full Speed werkt."}
]},
  {id:'capp', name:"Eerste keer voeden", next:"Ga door met \"Op de USB-module\".", steps:[
 {t:"Aansluiten op 5 V",info:true,body:`
  <p>Doe dit pas als alle multimetermetingen kloppen. Labvoeding <b>uit</b>, <b>5,0 V</b>, stroomgrens <b>300 mA</b>. Plus op <b>J2 pin 1</b>, min op <b>J2 pin 5</b>. Nog geen camera, geen USB.</p>`},
 {t:"Inschakelen",setting:"display van de labvoeding",exp:"ruim onder de grens",small:"noteer de stroom; schatting ≈ 0,2 A tijdens een stream",
  fail:"Op de stroomgrens: meteen uit. Voel welk onderdeel warm werd (U1, U2) en meld het hier."},
 {t:"Camera 1: 3,3 V",setting:"V DC",red:"pad van C3 dat níet GND is",black:"J2 pin 5",exp:"3,2 – 3,4 V",small:"en het hete pad van C7 (analoog): zelfde waarde",
  fail:"0 V: U1 start niet; kijk naar pin 16 (5 V in) en 17. Wel op C3, niet op C7: FB1."},
 {t:"Camera 1: 1,2 V",setting:"V DC",red:"pad van C11 dat níet GND is",black:"J2 pin 5",exp:"≈ 1,2 V",small:"",
  fail:"0 V: kijk naar U1 pin 18 en C11."},
 {t:"USB naar de PC",info:true,body:`
  <p>Voeding uit. Neem een doorgeknipte USB-kabel naar de PC. Nu mag de rode draad wél aan, de module krijgt zijn 5 V dan van de PC (haal de labvoeding weg):</p>
  <dl class="row"><dt>Rood (5 V)</dt><dd>J2 pin 1</dd><dt>Zwart (GND)</dt><dd>J2 pin 5</dd><dt>Groen (D+)</dt><dd>J2 pin 3</dd><dt>Wit (D-)</dt><dd>J2 pin 4</dd></dl>
  <div class="note">Houd de losse draadjes kort, onder 10 cm. Een USB-stroommeter ertussen is handig.</div>`},
 {t:"Camera op de PC",setting:"PowerShell",exp:"USB Video (VID_534D)",small:"zonder EEPROM standaard 534d:0021",
  pre:"<code>Get-PnpDevice -PresentOnly | Where-Object InstanceId -match 'VID_534D|VID_1A86' | Format-Table Status,FriendlyName,InstanceId</code>",
  fail:"Niets: D+ en D- omgewisseld, kristal Y1 en C14/C15, REXT R1, of U1 pin 32/33. Alleen Full Speed of 'onbekend apparaat': meestal de losse draadjes."},
 {t:"Beeld",setting:"Windows Camera-app, VLC of OBS",exp:"beeld van de camera",small:"camera op J1: pin 1 video (RCA-midden), pin 2 mantel",
  pre:"De camera krijgt zijn 12 V apart (labvoeding of achteruitlicht), niet van dit bord.",
  fail:"Wel apparaat, zwart beeld: kijk naar de videokabel, {C18} en de 12 V van de camera. Beeld rolt of zonder kleur: PAL/NTSC-instelling van de camera."},
 {t:"Status-LED",setting:"kijken",exp:"D1 brandt tijdens het streamen",small:"GPIO4 trekt de LED laag",
  fail:"Wel beeld, geen LED: LED verkeerd om (kathode aan de dichte kant van de silkscreen-haak) of R6 los. Niet erg voor de functie."}
]},
  {id:'capx', name:"Op de USB-module", next:"De capturemodule is klaar.", steps:[
 {t:"Op de USB-module",info:true,body:`
  <p>Alles uit. De USB-module rev 0.7 zit op het main board en is getest (eigen wizard). Steek J2 van de capturemodule in <b>J29</b> (vierkant pad op vierkant pad) en zet hem vast met een M2,5 × 11 standoff op H1, bovenop de standoff van de USB-module.</p>
  <p>Zekering in F4, jumper op JP1, labvoeding 12,0 V met een grens van 1,5 A. De capturemodule krijgt pas 5 V als de VIM3-voeding aan staat (+5V_CAP komt uit +5V_SYS via F7).</p>
  <div class="note">Kijk of de USB-A-sockets van de USB-module vrij blijven en of de draden van J12 en J7 eronder kunnen buigen.</div>`},
 {t:"5 V op de module",setting:"V DC",red:"pad van C1 dat níet GND is",black:"GND",exp:"4,9 – 5,2 V",small:"via F7 (1,1 A) op de USB-module",
  fail:"0 V: meet J29 pin 1 op de USB-module. Daar wel, hier niet: J2 slecht gesoldeerd of verkeerd ingestoken."},
 {t:"Camera via het main board",setting:"PowerShell (PC-kabel op J2 van het main board)",exp:"USB Video achter twee hubs",small:"hub 1 (main) → hub 2 (USB-module, poort 4)",
  fail:"Los werkte het wel: J29 pin 3/4, of U14 pin 1/2 op de USB-module."},
 {t:"In Android",setting:"adb shell",exp:"een /dev/video-apparaat en beeld in de RearViewCamera-app",small:"<code>ls /dev/video*</code>, <code>dmesg | grep -i uvc</code>",
  pre:"Zonder PC-kabel, met de VIM3 aangesloten. De RearViewCamera-app opent standaard de eerste externe camera.",
  fail:"Geen video-apparaat: kijk met <code>lsusb</code> of 534d:0021 er is. Wel apparaat, geen beeld in de app: Camera2/external camera-config van de build."}
]},
  ],
};
