import json, re, numpy as np
from scipy.optimize import linear_sum_assignment
D = json.load(open('pinpos.json'))
RP_GPIO_PIN = {0: 77, 1: 78, 2: 79, 3: 80, 4: 1, 5: 2, 6: 3, 7: 4, 8: 6, 9: 7, 10: 8, 11: 9, 12: 11, 13: 12, 14: 13, 15: 14,
               16: 16, 17: 17, 18: 18, 19: 19, 20: 20, 21: 21, 22: 22, 23: 23, 24: 25, 25: 26, 26: 27, 27: 28, 28: 36, 29: 37,
               30: 38, 31: 39, 32: 40, 33: 42, 34: 43, 35: 44, 36: 45, 37: 46, 38: 47, 39: 48,
               40: 49, 41: 52, 42: 53, 43: 54, 44: 55, 45: 56, 46: 57, 47: 58}
OLD = {0: "MCU_GNSS_TX", 1: "MCU_GNSS_RX", 2: "MCU_ACC_IN", 3: "MCU_REV_IN", 4: "LUX_SDA", 5: "LUX_SCL", 6: "MCU_ILLUM_IN",
       7: "MCU_PARK_IN", 8: "MCU_PWR_KEY", 9: "MCU_AMP_EN", 10: "MCU_BL_EN", 11: "MCU_BL_PWM", 12: "MCU_GNSS_EN",
       13: "MCU_SBC_SENSE", 14: "MCU_SERVICE", 15: "MCU_DAC_MUTE", 16: "MCU_BTN_SCREEN", 17: "MCU_BTN_VOLUP",
       18: "MCU_GNSS_RST", 19: "MCU_GNSS_PPS", 20: "EXP_GP20", 21: "EXP_GP21", 22: "MCU_BTN_VOLDN",
       23: "MCU_USBP_FAULT1", 24: "MCU_USBP_FAULT2", 25: "MCU_LED", 26: "MCU_USBP_PG", 27: "MCU_BTN_MUTE",
       28: "MCU_VIM3_PWR_EN", 29: "MCU_GNSS_SAFEBOOT", 30: "EXP_GP30", 31: "EXP_GP31",
       32: "EXP_GP32", 33: "EXP_GP33", 34: "EXP_GP34", 35: "EXP_GP35", 36: "EXP_GP36", 37: "EXP_GP37", 38: "EXP_GP38", 39: "EXP_GP39",
       40: "MCU_VBAT_ADC", 41: "MCU_5VSYS_ADC", 42: "MCU_TEMP_ADC", 43: "MCU_HUB_RST"}
RAILS = {'GND', '/+3V3_MCU', '/+5V_AON', '/+3V3_GNSS', '/VIM3_3V3', '/HUB_3V3', '/+5V_SYS'}
def targets(net, depth=0, seen=None):
    seen = seen or {net}; pts = []
    for ref, pn, x, y, others in D['nets'].get(net, []):
        if ref == 'U20': continue
        if re.match(r'^[RC]\d', ref) and len(others) == 1:
            o = others[0]
            if o in RAILS or o == '': continue
            if depth < 2 and o not in seen:
                seen.add(o); sub = targets(o, depth + 1, seen)
                pts += sub if sub else [(x, y)]
            else: pts.append((x, y))
        else: pts.append((x, y))
    return pts
def cent(net):
    p = targets('/' + net) or [(x, y) for r, _, x, y, _ in D['nets'].get('/' + net, []) if r != 'U20']
    if not p: return None
    return (sum(a for a, _ in p) / len(p), sum(b for _, b in p) / len(p))
pos = {g: D['u20'][str(RP_GPIO_PIN[g])] for g in RP_GPIO_PIN}
# fixed: ADC on 40-42, keep. Pairs: GNSS UART (TX at n%4==0), LUX I2C (SDA even, SCL odd)
fixed = {40: "MCU_VBAT_ADC", 41: "MCU_5VSYS_ADC", 42: "MCU_TEMP_ADC"}
def pcost(a, b, na, nb):
    ca, cb = cent(na), cent(nb)
    return np.hypot(pos[a][0] - ca[0], pos[a][1] - ca[1]) + np.hypot(pos[b][0] - cb[0], pos[b][1] - cb[1])
free = [g for g in range(48) if g not in fixed]
uart = min(((n, n + 1) for n in range(0, 40, 4) if n not in fixed), key=lambda p: pcost(*p, "MCU_GNSS_TX", "MCU_GNSS_RX"))
i2c = min(((n, n + 1) for n in range(0, 40, 2) if n not in uart and n + 1 not in uart), key=lambda p: pcost(*p, "LUX_SDA", "LUX_SCL"))
fixed.update({uart[0]: "MCU_GNSS_TX", uart[1]: "MCU_GNSS_RX", i2c[0]: "LUX_SDA", i2c[1]: "LUX_SCL"})
sig = [n for n in OLD.values() if n not in fixed.values() and not n.startswith('EXP')]
# expansion slots: J10 pins 2,3,4,8 ; J21 pins 2..9 -> header pin positions
def hdr(ref, pin):
    for net, lst in D['nets'].items():
        for r, pn, x, y, o in lst:
            if r == ref and pn == pin: return (x, y)
# J10 pins 2/3 stay a UART TX/RX pair (future K-line board)
def kcost(n):
    a, b = hdr('J10', '2'), hdr('J10', '3')
    return np.hypot(pos[n][0] - a[0], pos[n][1] - a[1]) + np.hypot(pos[n + 1][0] - b[0], pos[n + 1][1] - b[1])
kl = min((n for n in range(0, 40, 4) if n not in fixed and n + 1 not in fixed), key=kcost)
fixed.update({kl: 'J10.2', kl + 1: 'J10.3'}); print('kline uart', kl)
slots = [('J10', p) for p in ('4', '8')] + [('J21', str(p)) for p in range(2, 10)]
items = [(n, cent(n)) for n in sig] + [(f'{r}.{p}', hdr(r, p)) for r, p in slots]
gp = [g for g in range(48) if g not in fixed and g < 44]   # 44-47 stay unused (ADC-capable spares)
C = np.array([[np.hypot(pos[g][0] - c[0], pos[g][1] - c[1]) for g in gp] for _, c in items])
r, c = linear_sum_assignment(C)
new = dict(fixed)
for i, j in zip(r, c): new[gp[j]] = items[i][0]
old_cost = sum(np.hypot(pos[g][0] - cent(n)[0], pos[g][1] - cent(n)[1]) for g, n in OLD.items() if not n.startswith('EXP'))
print('uart', uart, 'i2c', i2c, 'unused', sorted(set(range(48)) - set(new)))
for g in sorted(new): print(g, RP_GPIO_PIN[g], OLD.get(g), '->', new[g])
json.dump({str(k): v for k, v in new.items()}, open('newmap.json', 'w'))
