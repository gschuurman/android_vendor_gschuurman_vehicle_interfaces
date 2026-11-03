# Stencilmal hoofdbord rev 0.6

Eén printdeel om soldeerpasta op het hoofdbord (100 x 100 mm, 1,6 mm) te zetten met de frameloze JLCPCB-stencil,
die precies even groot is als de print.

| Bestand | Wat |
|---|---|
| `stencil_jig_rev06.stl` | de mal, 140 x 140 x 4,69 mm |
| `stencil_jig_rev06.scad` | dezelfde vorm in OpenSCAD, met alle maten als parameter |
| `stencil_jig_gen.py` | het script dat de STL maakte (trimesh + manifold3d) |

## Hoe het werkt

- Eén uitsparing van 100,3 x 100,3 mm, 1,69 mm diep. De print gaat erin, de stencil komt er bovenop in dezelfde
  uitsparing. Omdat beide 100 x 100 mm zijn, liggen hun randen gelijk en dus ook de openingen op de pads.
- Diepte = print (1,6) + stencil (0,12) - 0,03: de stencil steekt net boven de rand uit, zodat de rakel hem goed
  op de print drukt.
- Ronde uitsparingen in de hoeken: een stencil met scherpe hoeken past ook.
- Inkepingen links en rechts om stencil en print er met je vinger of een pincet uit te halen.

## Printen

PLA of PETG, laaghoogte 0,2 mm (of 0,1 mm voor een nauwkeuriger diepte), plat op het bed, geen support.

## Gebruik

1. **Hoogte controleren.** Print en stencil erin, liniaal eroverheen. De stencil moet gelijk liggen of iets
   uitsteken. Ligt hij lager (dunnere print of dikkere laag), leg dan kapton of papier onder de print.
2. **Richting.** Leg print en stencil in dezelfde richting (bijv. de 40-pins header allebei boven). Een
   verkeerde draaiing zie je meteen, want dan vallen de openingen niet op de pads.
3. **Pasta.** Druk de stencil met twee vingers plat, pasta langs de bovenrand, rakel in één beweging onder
   ongeveer 45 graden over de hele print.
4. **Optillen.** Stencil bij een inkeping recht omhoog tillen, niet schuiven. Daarna de print eruit.

Is je stencil dikker of dunner dan 0,12 mm, of is de print anders dan 1,6 mm, pas dan `stencil_t` of `pcb_t`
aan in het .scad-bestand.
