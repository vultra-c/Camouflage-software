#!/usr/bin/env python3
"""生成 src/common/icon.png：黑底红色LED数码管图标。

特性：4x超采样抗锯齿 / 对角渐变金属表壳环 / 双层辉光(bloom) /
对角玻璃反光 / 192x192 RGBA 圆角方块。
用法：python3 scripts/gen-icon.py
"""
import struct
import zlib

S = 4                      # 超采样倍数
N = 192                    # 最终尺寸
W = H = N * S              # 768x768 绘制画布

# ---------- 基础绘图工具 ----------

def rounded_rect_inside(x, y, x0, y0, x1, y1, r, inset=0):
    ix0, iy0, ix1, iy1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
    rr = max(r - inset, 0)
    if x < ix0 or x > ix1 or y < iy0 or y > iy1:
        return False
    if x < ix0 + rr and y < iy0 + rr:
        return (x - (ix0 + rr)) ** 2 + (y - (iy0 + rr)) ** 2 <= rr * rr
    if x > ix1 - rr and y < iy0 + rr:
        return (x - (ix1 - rr)) ** 2 + (y - (iy0 + rr)) ** 2 <= rr * rr
    if x < ix0 + rr and y > iy1 - rr:
        return (x - (ix0 + rr)) ** 2 + (y - (iy1 - rr)) ** 2 <= rr * rr
    if x > ix1 - rr and y > iy1 - rr:
        return (x - (ix1 - rr)) ** 2 + (y - (iy1 - rr)) ** 2 <= rr * rr
    return True

def fill_poly(buf, poly):
    """扫描线填充多边形（bbox内逐点奇偶测试）。"""
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x0, x1 = max(int(min(xs)), 0), min(int(max(xs)) + 1, W)
    y0, y1 = max(int(min(ys)), 0), min(int(max(ys)) + 1, H)
    n = len(poly)
    for y in range(y0, y1):
        py = y + 0.5
        for x in range(x0, x1):
            px = x + 0.5
            inside = False
            j = n - 1
            for i in range(n):
                xi, yi = poly[i]
                xj, yj = poly[j]
                if (yi > py) != (yj > py):
                    if px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi:
                        inside = not inside
                j = i
            if inside:
                buf[y * W + x] = 1

def box_blur(src, radius, passes=2):
    """可分离盒式模糊（积分滑窗），近似高斯。"""
    out = list(src)
    inv = 1.0 / (2 * radius + 1)
    for _ in range(passes):
        tmp = [0.0] * (W * H)
        for y in range(H):
            row = y * W
            acc = 0.0
            for x in range(-radius, radius + 1):
                acc += out[row + min(max(x, 0), W - 1)]
            for x in range(W):
                tmp[row + x] = acc * inv
                acc -= out[row + min(max(x - radius, 0), W - 1)]
                acc += out[row + min(max(x + radius + 1, 0), W - 1)]
        for x in range(W):
            acc = 0.0
            for y in range(-radius, radius + 1):
                acc += tmp[min(max(y, 0), H - 1) * W + x]
            for y in range(H):
                out[y * W + x] = acc * inv
                acc -= tmp[min(max(y - radius, 0), H - 1) * W + x]
                acc += tmp[min(max(y + radius + 1, 0), H - 1) * W + x]
    return out

# ---------- 7段码数字 ----------

def seg_h(x0, x1, y0, t):
    """水平段：两端斜切六边形。"""
    h = t // 2
    return [(x0 + h, y0), (x1 - h, y0), (x1, y0 + h), (x1 - h, y0 + t),
            (x0 + h, y0 + t), (x0, y0 + h)]

def seg_v(x0, y0, y1, t):
    """垂直段：两端斜切六边形。"""
    h = t // 2
    return [(x0, y0 + h), (x0 + h, y0), (x0 + t, y0 + h), (x0 + t, y1 - h),
            (x0 + h, y1), (x0, y1 - h)]

# a=1 b=2 c=4 d=8 e=16 f=32 g=64
DIGIT_SEGS = {
    0: 1 | 2 | 4 | 8 | 16 | 32,
    1: 2 | 4,
    2: 1 | 2 | 8 | 16 | 64,
    3: 1 | 2 | 4 | 8 | 64,
    4: 2 | 4 | 32 | 64,
    5: 1 | 4 | 8 | 32 | 64,
    6: 1 | 4 | 8 | 16 | 32 | 64,
    7: 1 | 2 | 4,
    8: 1 | 2 | 4 | 8 | 16 | 32 | 64,
    9: 1 | 2 | 4 | 8 | 32 | 64,
}

def draw_digit(mask, d, dx, dy, dw, dh, t):
    on = DIGIT_SEGS[d]
    hm = t // 2
    hx0, hx1 = dx + hm + 7, dx + dw - hm - 7
    vy0 = dy + hm + 9
    vy1 = dy + dh // 2 - t // 2 - 4
    vy2 = dy + dh // 2 + t // 2 + 4
    vy3 = dy + dh - hm - 9
    lx, rx = dx, dx + dw - t
    gy = dy + dh // 2 - t // 2
    if on & 1:
        fill_poly(mask, seg_h(hx0, hx1, dy, t))
    if on & 64:
        fill_poly(mask, seg_h(hx0, hx1, gy, t))
    if on & 8:
        fill_poly(mask, seg_h(hx0, hx1, dy + dh - t, t))
    if on & 32:
        fill_poly(mask, seg_v(lx, vy0, vy1, t))
    if on & 2:
        fill_poly(mask, seg_v(rx, vy0, vy1, t))
    if on & 16:
        fill_poly(mask, seg_v(lx, vy2, vy3, t))
    if on & 4:
        fill_poly(mask, seg_v(rx, vy2, vy3, t))

def main():
    radius = 128            # 圆角（192 尺度约 32）
    ring_w = 16             # 表壳环宽（768 尺度）

    # 1) alpha 蒙版：圆角方块
    alpha = bytearray(W * H)
    for y in range(H):
        for x in range(W):
            if rounded_rect_inside(x, y, 0, 0, W - 1, H - 1, radius * S // 4):
                alpha[y * W + x] = 255

    # 2) 段码蒙版 "20:35"（更粗壮：120x216，厚度22）
    mask = bytearray(W * H)
    dw, dh, t = 120, 216, 22
    gap, colon_w = 14, 40
    total = 4 * dw + colon_w + 4 * gap
    x0 = (W - total) // 2
    y0 = (H - dh) // 2 - 14            # 视觉重心略上移
    xs = [x0, x0 + dw + gap]
    xc = x0 + 2 * dw + 2 * gap
    xs += [xc + colon_w + gap, xc + colon_w + gap + dw + gap]
    for i, d in enumerate([2, 0, 3, 5]):
        draw_digit(mask, d, xs[i], y0, dw, dh, t)
    # 冒号
    cd = 24
    cx = xc + (colon_w - cd) // 2
    for yy in (y0 + dh // 2 - 40, y0 + dh // 2 + 16):
        fill_poly(mask, [(cx, yy), (cx + cd, yy), (cx + cd, yy + cd), (cx, yy + cd)])

    # 3) 双层辉光：宽晕 + 紧凑 bloom
    src = [float(v) for v in mask]
    glow_wide = box_blur(src, 26, passes=2)
    glow_tight = box_blur(src, 8, passes=1)

    # 4) 合成
    rgb = bytearray(W * H * 3)
    ring_in = radius * S // 4
    for y in range(H):
        for x in range(W):
            i = y * W + x
            if alpha[i] == 0:
                continue
            in_ring = not rounded_rect_inside(x, y, 0, 0, W - 1, H - 1, radius * S // 4, ring_w)
            if in_ring:
                # 金属渐变：左上亮 → 右下暗（对角）
                d = (x + y) / float(W + H - 2)
                v = int(0x78 + (0x14 - 0x78) * d)
                r = g = b = v
            else:
                # 屏幕内部：黑底 + 红色辉光 + 亮段
                gw = min(glow_wide[i], 1.0)
                gt = min(glow_tight[i], 1.0)
                if mask[i]:
                    r, g, b = 255, 46, 16
                else:
                    # 宽晕 + 紧凑bloom 叠加（红色）
                    glow = min(gw * 0.72 + gt * 0.55, 1.0)
                    r = int(255 * glow)
                    g = int(58 * glow)
                    b = int(14 * glow)
            # 玻璃反光：左上→右下的对角高光带（4%白），亮段不受影响
            if not mask[i]:
                dnorm = (x + y) / float(W + H - 2)
                if 0.24 < dnorm < 0.34:
                    edge = 1.0 - abs(dnorm - 0.29) / 0.05
                    add = int(14 * edge)
                    r = min(r + add, 255)
                    g = min(g + add, 255)
                    b = min(b + add, 255)
            rgb[i * 3] = r
            rgb[i * 3 + 1] = g
            rgb[i * 3 + 2] = b

    # 5) 4x 下采样 → 192x192 RGBA（alpha加权，边缘干净）
    out = bytearray()
    for y in range(N):
        out += b'\x00'
        for x in range(N):
            sr = sg = sb = sa = 0
            for dy in range(S):
                base = (y * S + dy) * W + x * S
                for dx in range(S):
                    i = base + dx
                    a = alpha[i]
                    if a:
                        sr += rgb[i * 3] * a
                        sg += rgb[i * 3 + 1] * a
                        sb += rgb[i * 3 + 2] * a
                    sa += a
            if sa:
                out += bytes((sr // sa, sg // sa, sb // sa, sa // (S * S)))
            else:
                out += bytes((0, 0, 0, 0))

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', N, N, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(bytes(out), 9))
    png += chunk(b'IEND', b'')
    with open('src/common/icon.png', 'wb') as f:
        f.write(png)
    print('icon.png written:', len(png), 'bytes')

if __name__ == '__main__':
    main()
