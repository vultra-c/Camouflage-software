#!/usr/bin/env python3
"""生成 src/common/icon.png：黑底红色LED数码管图标，4x超采样抗锯齿+辉光。"""
import struct
import zlib

S = 4                      # 超采样倍数
N = 192                    # 最终尺寸
W = H = N * S              # 768x768 绘制画布

# ---------- 基础绘图工具 ----------

def rounded_rect_mask(x0, y0, x1, y1, r):
    """判断点是否在圆角矩形内（逐像素）。"""
    def inside(px, py, inset=0):
        ix0, iy0, ix1, iy1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
        rr = max(r - inset, 0)
        if px < ix0 or px > ix1 or py < iy0 or py > iy1:
            return False
        cx = ix0 + rr if px < ix0 + rr else (ix1 - rr if px > ix1 - rr else px)
        cy = iy0 + rr if py < iy0 + rr else (iy1 - rr if py > iy1 - rr else py)
        if px < ix0 + rr and py < iy0 + rr:
            return (px - (ix0 + rr)) ** 2 + (py - (iy0 + rr)) ** 2 <= rr * rr
        if px > ix1 - rr and py < iy0 + rr:
            return (px - (ix1 - rr)) ** 2 + (py - (iy0 + rr)) ** 2 <= rr * rr
        if px < ix0 + rr and py > iy1 - rr:
            return (px - (ix0 + rr)) ** 2 + (py - (iy1 - rr)) ** 2 <= rr * rr
        if px > ix1 - rr and py > iy1 - rr:
            return (px - (ix1 - rr)) ** 2 + (py - (iy1 - rr)) ** 2 <= rr * rr
        return True
    return inside

def fill_poly(buf, poly, val=1):
    """扫描线填充多边形（bbox内逐点测试）。"""
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
                buf[y * W + x] = val

def box_blur(src, radius, passes=2):
    """可分离盒式模糊，近似高斯（积分图实现）。"""
    out = list(src)
    for _ in range(passes):
        # 水平
        tmp = [0.0] * (W * H)
        for y in range(H):
            row = y * W
            acc = 0.0
            for x in range(-radius, radius + 1):
                acc += out[row + min(max(x, 0), W - 1)]
            for x in range(W):
                tmp[row + x] = acc / (2 * radius + 1)
                acc -= out[row + min(max(x - radius, 0), W - 1)]
                acc += out[row + min(max(x + radius + 1, 0), W - 1)]
        # 垂直
        for x in range(W):
            acc = 0.0
            for y in range(-radius, radius + 1):
                acc += tmp[min(max(y, 0), H - 1) * W + x]
            for y in range(H):
                out[y * W + x] = acc / (2 * radius + 1)
                acc -= tmp[min(max(y - radius, 0), H - 1) * W + x]
                acc += tmp[min(max(y + radius + 1, 0), H - 1) * W + x]
    return out

# ---------- 7段码数字 ----------

def seg_h_solid(x0, x1, y0, t):
    """水平段：两端斜切的六边形。"""
    h = t // 2
    return [(x0 + h, y0), (x1 - h, y0), (x1, y0 + h), (x1 - h, y0 + t),
            (x0 + h, y0 + t), (x0, y0 + h)]

def seg_v_solid(x0, y0, y1, t):
    """垂直段：两端斜切的六边形。"""
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
    """在 mask 上绘制一个7段码数字。"""
    mask_on = DIGIT_SEGS[d]
    hm = t // 2
    hx0, hx1 = dx + hm + 6, dx + dw - hm - 6      # 横段左右缩进
    vy0 = dy + hm + 8                              # 上竖段起点
    vy1 = dy + dh // 2 - t // 2 - 3                # 上竖段终点
    vy2 = dy + dh // 2 + t // 2 + 3                # 下竖段起点
    vy3 = dy + dh - hm - 8                         # 下竖段终点
    lx, rx = dx, dx + dw - t
    gy = dy + dh // 2 - t // 2                     # 中横段
    if mask_on & 1:    fill_poly(mask, seg_h_solid(hx0, hx1, dy, t))
    if mask_on & 64:   fill_poly(mask, seg_h_solid(hx0, hx1, gy, t))
    if mask_on & 8:    fill_poly(mask, seg_h_solid(hx0, hx1, dy + dh - t, t))
    if mask_on & 32:   fill_poly(mask, seg_v_solid(lx, vy0, vy1, t))
    if mask_on & 2:    fill_poly(mask, seg_v_solid(rx, vy0, vy1, t))
    if mask_on & 16:   fill_poly(mask, seg_v_solid(lx, vy2, vy3, t))
    if mask_on & 4:    fill_poly(mask, seg_v_solid(rx, vy2, vy3, t))

def main():
    # 1) 背景：圆角矩形 + 表壳边环
    alpha = bytearray(W * H)
    ring = bytearray(W * H)
    inside_outer = rounded_rect_mask(0, 0, W - 1, H - 1, 110 * S // 4)
    inside_inner = rounded_rect_mask(0, 0, W - 1, H - 1, 110 * S // 4)
    ring_px = 14  # 表壳环宽
    for y in range(H):
        for x in range(W):
            if inside_outer(x, y):
                alpha[y * W + x] = 255
                if not inside_inner(x, y, ring_px):
                    ring[y * W + x] = 1

    # 2) 段码蒙版 "20:35"
    mask = bytearray(W * H)
    dw, dh, t = 108, 200, 20
    gap = 12
    colon_w = 36
    total = 4 * dw + colon_w + 4 * gap
    x = (W - total) // 2
    y0 = (H - dh) // 2 - 16
    digits = [2, 0, 3, 5]
    slots = [(x, digits[0]), (x + dw + gap, digits[1])]
    xcolon = x + 2 * dw + gap + gap
    slots.append((xcolon + colon_w + gap, digits[2]))
    slots.append((xcolon + colon_w + gap + dw + gap, digits[3]))
    for dx, d in slots:
        draw_digit(mask, d, dx, y0, dw, dh, t)
    # 冒号两点
    cd = 20
    cx = xcolon + (colon_w - cd) // 2
    for yy in (y0 + dh // 2 - 34, y0 + dh // 2 + 14):
        fill_poly(mask, [(cx, yy), (cx + cd, yy), (cx + cd, yy + cd), (cx, yy + cd)])

    # 3) 辉光
    src = [float(v) for v in mask]
    glow = box_blur(src, 14 * S // 4, passes=2)

    # 4) 合成
    rgb = bytearray(W * H * 3)
    for i in range(W * H):
        if alpha[i] == 0:
            continue
        if ring[i]:
            rgb[i * 3] = rgb[i * 3 + 1] = rgb[i * 3 + 2] = 0x2a
            continue
        g = glow[i]
        if mask[i]:
            r, gg, b = 255, 42, 12
        else:
            r = int(255 * min(g * 0.85, 1.0))
            gg = int(46 * min(g * 0.85, 1.0))
            b = int(10 * min(g * 0.85, 1.0))
        rgb[i * 3], rgb[i * 3 + 1], rgb[i * 3 + 2] = r, gg, b

    # 5) 4x 下采样 → 192x192 RGBA
    out = bytearray()
    for y in range(N):
        out += b'\x00'
        for x in range(N):
            sr = sg = sb = sa = 0
            for dy in range(S):
                row = (y * S + dy) * W + x * S
                for dx in range(S):
                    i = row + dx
                    a = alpha[i]
                    if a:
                        sr += rgb[i * 3] * a
                        sg += rgb[i * 3 + 1] * a
                        sb += rgb[i * 3 + 2] * a
                    sa += a
            cnt = S * S
            if sa:
                a_avg = sa // cnt
                pa = sa or 1
                out += bytes((sr // pa, sg // pa, sb // pa, max(a_avg, 1) if a_avg else 0))
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
