set -e
cd ~/kl
/usr/bin/python3 -c "
import pcbnew
b=pcbnew.LoadBoard('kline_module/kline_module.kicad_pcb'); print(pcbnew.ExportSpecctraDSN(b,'kline_module/kline_module.dsn'))"
(cd fr && timeout 300 java -jar fr2.jar -de /root/kl/kline_module/kline_module.dsn -do /root/kl/kline_module/kline_module.ses -mp 100 --gui.enabled=false > ~/kl/fr.log 2>&1 || true)
ls -la kline_module/kline_module.ses
