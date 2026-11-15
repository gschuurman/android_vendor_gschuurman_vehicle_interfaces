set -e
cd ~/kl
/usr/bin/python3 gen_pcb.py | grep -v "J1 pad\|CY"
bash route.sh > /dev/null 2>&1
/usr/bin/python3 import_ses.py && /usr/bin/python3 fixup.py 2>&1 | grep -v leak
/usr/bin/python3 zones.py
grep -E 'Found' kline_module/drc.rpt; grep '^\[' kline_module/drc.rpt | grep -v lib_footprint | sort | uniq -c
