import re, sys

def parse(path):
    raw = open(path, encoding='utf-8').read()
    blocks = [b for b in raw.strip().split('\n\n') if b.strip()]
    out = []
    for b in blocks:
        lines = b.split('\n')
        m = re.match(r'(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)', lines[1])
        s = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 1000
        e = int(m[5]) * 3600 + int(m[6]) * 60 + int(m[7]) + int(m[8]) / 1000
        out.append((s, e, ''.join(lines[2:])))
    return out

def stats(name, entries, dur=5873.0):
    total_speech = sum(e - s for s, e, _ in entries)
    covered = 0.0
    cur_s, cur_e = None, None
    for s, e, _ in sorted(entries):
        if cur_s is None:
            cur_s, cur_e = s, e
        elif s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            covered += cur_e - cur_s
            cur_s, cur_e = s, e
    if cur_s is not None:
        covered += cur_e - cur_s
    zero = sum(1 for s, e, _ in entries if e - s <= 0.001)
    short = sum(1 for s, e, _ in entries if e - s < 0.8)
    long_ = [(round(s), round(e - s, 1)) for s, e, _ in entries if e - s > 12]
    gaps = []
    prev = 0.0
    for s, e, _ in sorted(entries):
        if s - prev > 60:
            gaps.append((round(prev), round(s), round(s - prev)))
        prev = max(prev, e)
    print(f"== {name}: {len(entries)} 条 | 时间轴覆盖 {covered:.0f}s ({covered/dur*100:.1f}%) | "
          f"0时长 {zero} | <0.8s {short} | >12s {len(long_)}{long_[:4]} | >60s空白 {len(gaps)}{gaps[:5]}")

def at(entries, t0, t1, label):
    sel = [(s, e, x) for s, e, x in entries if s >= t0 and s < t1]
    print(f"-- {label} [{t0}-{t1}s] {len(sel)} 条:")
    for s, e, x in sel[:14]:
        print(f"   {int(s//60)}:{int(s%60):02d} {x[:60]}")

if __name__ == '__main__':
    purf = parse('/home/hatch/workspace/colab-purfview/out/114820.srt')
    stats('Purfview XXL (JA)', purf)
    at(purf, 3141, 3227, 'Purfview 幻觉段 52:21-53:47')
    if len(sys.argv) > 1:
        cr = parse(sys.argv[1])
        stats('ChickenRice 翻译版 (ZH)', cr)
        at(cr, 3141, 3227, 'ChickenRice-ZH 同时间段')
        at(cr, 0, 120, 'ChickenRice-ZH 开头')
    if len(sys.argv) > 2:
        ja = parse(sys.argv[2])
        stats('ChickenRice 转录版 (JA)', ja)
        at(ja, 3141, 3227, 'ChickenRice-JA 同时间段')
        print('マンゴー:', sum(x.count('マンゴー') for _, _, x in ja),
              '| マンコ:', sum(x.count('マンコ') for _, _, x in ja),
              '| 仲出し:', sum(x.count('仲出し') for _, _, x in ja),
              '| 中出し:', sum(x.count('中出し') for _, _, x in ja),
              '| 精神:', sum(x.count('精神') for _, _, x in ja),
              '| 精子:', sum(x.count('精子') for _, _, x in ja))
