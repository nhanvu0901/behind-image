# Equivalence report: bti.engine vs the benchmark `frame_at`

Old reference: `build_v2.py` `frame_fn` (copy in `.scratch/engine/old`, same Mac, same fonts). New: `Project.frame_at(t, 1920)` on `projects/arnolfini`.
Metric: PSNR (dB) over the 1920x1080 BGR frames; requirement >= 40 dB.

- samples: **292** (every card, every overlay onset and middle, every shot start and middle, the end fade)
- PSNR min / median / max: **56.93 / 99.00 / 99.00 dB** (99 = bit-identical)
- identical frames (PSNR 99): 227
- below threshold: **0**

## Exceptions

None: every sampled frame is at or above the threshold.

## Notes on the residual differences

Most frames are bit-identical (99 dB). The lower values (lowest 57 dB at the start of the mirror push shot s0058, then 69-73 dB, all far above the 40 dB bar) come from deliberate approximations in the export:
- anchors are stored with 0.1 ms resolution (`off` rounded to 4 decimals) and camera zoom with 6 decimals, so camera and overlay values differ from the benchmark by about 1e-6 relative (this alone gives the 70+ dB frames);
- the mirror push/drift camera track (shot s0058) was sampled every 0.25 s in the benchmark; the exporter reduces it with a 0.3 px tolerance (Ramer-Douglas-Peucker) to a few keys;
- 3 overlay ends were clamped to their shot end (the storyboard rule: overlays lie inside their shot); only a fade tail that the benchmark clipped at the shot cut is affected.
Fonts are the same fallback on both sides (Futura on this Mac); there is no font-related difference to report.
Timing semantics kept from the benchmark: spotlight ramp-out starts at the overlay end, ring uses its own draw/hold/fade, the AN-05 rulers are pinned with `frame_zoom`.

## All samples

| t (s) | kind | shot | technique | PSNR (dB) |
|---|---|---|---|---|
| 0.050 | shot start | s0001 | CAM-01 | 71.72 |
| 5.585 | shot middle | s0001 | CAM-01 | 72.62 |
| 11.220 | shot start | s0002 | CAM-03 | 72.94 |
| 20.170 | shot middle | s0002 | CAM-03 | 82.52 |
| 29.220 | shot start | s0003 | STATIC-01 | 76.64 |
| 30.070 | overlay onset | s0003 | AN-05 | 84.31 |
| 32.120 | overlay middle | s0003 | AN-05 | 79.96 |
| 33.725 | shot middle | s0003 | STATIC-01 | 88.60 |
| 38.330 | shot start | s0004 | CAM-05 | 99.00 |
| 38.820 | overlay onset | s0004 | HI-01 | 99.00 |
| 39.170 | overlay middle | s0004 | HI-01 | 99.00 |
| 40.560 | overlay onset | s0004 | HI-01 | 99.00 |
| 40.680 | overlay onset | s0004 | X-ANN-01 | 99.00 |
| 42.080 | overlay middle | s0004 | X-ANN-01 | 99.00 |
| 42.855 | shot middle | s0004 | CAM-05 | 99.00 |
| 43.895 | overlay middle | s0004 | HI-01 | 99.00 |
| 47.480 | shot start | s0005 | CAM-05 | 99.00 |
| 52.300 | shot middle | s0005 | CAM-05 | 99.00 |
| 57.220 | shot start | s0006 | STATIC-01 | 99.00 |
| 60.600 | shot middle | s0006 | STATIC-01 | 99.00 |
| 64.080 | shot start | s0007 | CAM-05 | 99.00 |
| 65.660 | shot middle | s0007 | CAM-05 | 99.00 |
| 67.340 | shot start | s0008 | CAM-05 | 99.00 |
| 70.800 | shot middle | s0008 | CAM-05 | 99.00 |
| 74.360 | shot start | s0009 | X-CARD-02 | 99.00 |
| 74.910 | card | s0009 | X-CARD-02 THE ARNOLFINI PORTRAIT | 99.00 |
| 75.760 | shot middle | s0009 | X-CARD-02 | 99.00 |
| 76.210 | card (text gone) | s0009 | X-CARD-02 | 99.00 |
| 77.260 | shot start | s0010 | X-CARD-01 | 99.00 |
| 77.810 | card | s0010 | X-CARD-01 THE MERCHANT CITY | 99.00 |
| 78.610 | shot middle | s0010 | X-CARD-01 | 99.00 |
| 79.110 | card (text gone) | s0010 | X-CARD-01 | 99.00 |
| 80.060 | shot start | s0011 | X-LAY-01 | 77.78 |
| 80.810 | overlay onset | s0011 | X-ANN-02 | 84.27 |
| 82.210 | overlay middle | s0011 | X-ANN-02 | 82.87 |
| 90.340 | shot middle | s0011 | X-LAY-01 | 74.76 |
| 100.720 | shot start | s0012 | STATIC-06 | 99.00 |
| 110.260 | shot middle | s0012 | STATIC-06 | 99.00 |
| 119.900 | shot start | s0013 | STATIC-01 | 99.00 |
| 126.655 | shot middle | s0013 | STATIC-01 | 99.00 |
| 133.510 | shot start | s0014 | X-LAY-01 | 78.12 |
| 134.260 | overlay onset | s0014 | X-ANN-02 | 79.78 |
| 135.460 | shot middle | s0014 | X-LAY-01 | 80.48 |
| 135.660 | overlay middle | s0014 | X-ANN-02 | 78.60 |
| 137.510 | shot start | s0015 | STATIC-01 | 99.00 |
| 142.345 | shot middle | s0015 | STATIC-01 | 99.00 |
| 147.280 | shot start | s0016 | X-LAY-01 | 99.00 |
| 148.030 | overlay onset | s0016 | X-ANN-02 | 99.00 |
| 149.390 | shot middle | s0016 | X-LAY-01 | 84.28 |
| 149.430 | overlay middle | s0016 | X-ANN-02 | 77.92 |
| 151.600 | shot start | s0017 | X-LAY-01 | 79.30 |
| 152.350 | overlay onset | s0017 | X-ANN-02 | 81.26 |
| 153.750 | overlay middle | s0017 | X-ANN-02 | 80.28 |
| 154.435 | shot middle | s0017 | X-LAY-01 | 80.36 |
| 157.370 | shot start | s0018 | STATIC-01 | 99.00 |
| 162.525 | shot middle | s0018 | STATIC-01 | 99.00 |
| 167.780 | shot start | s0019 | X-CARD-01 | 99.00 |
| 168.330 | card | s0019 | X-CARD-01 THE ARNOLFINIS | 99.00 |
| 169.130 | shot middle | s0019 | X-CARD-01 | 99.00 |
| 169.630 | card (text gone) | s0019 | X-CARD-01 | 99.00 |
| 170.580 | shot start | s0020 | STATIC-01 | 99.00 |
| 175.590 | overlay onset | s0020 | STATIC-08 | 99.00 |
| 177.190 | overlay middle | s0020 | STATIC-08 | 99.00 |
| 179.150 | overlay onset | s0020 | STATIC-08 | 99.00 |
| 180.460 | shot middle | s0020 | STATIC-01 | 99.00 |
| 180.650 | overlay middle | s0020 | STATIC-08 | 99.00 |
| 190.440 | shot start | s0021 | STATIC-01 | 99.00 |
| 194.750 | overlay onset | s0021 | STATIC-09 | 99.00 |
| 195.155 | shot middle | s0021 | STATIC-01 | 99.00 |
| 195.780 | overlay middle | s0021 | STATIC-09 | 99.00 |
| 197.950 | overlay onset | s0021 | STATIC-09 | 99.00 |
| 198.835 | overlay middle | s0021 | STATIC-09 | 99.00 |
| 199.970 | shot start | s0022 | STATIC-01 | 99.00 |
| 204.615 | shot middle | s0022 | STATIC-01 | 99.00 |
| 209.360 | shot start | s0023 | X-LAY-01 | 99.00 |
| 210.110 | overlay onset | s0023 | X-ANN-02 | 99.00 |
| 211.310 | shot middle | s0023 | X-LAY-01 | 99.00 |
| 211.510 | overlay middle | s0023 | X-ANN-02 | 99.00 |
| 213.360 | shot start | s0024 | STATIC-01 | 99.00 |
| 216.385 | shot middle | s0024 | STATIC-01 | 99.00 |
| 219.510 | shot start | s0025 | CAM-04 | 99.00 |
| 224.960 | shot middle | s0025 | CAM-04 | 99.00 |
| 230.510 | shot start | s0026 | CAM-05 | 99.00 |
| 235.620 | shot middle | s0026 | CAM-05 | 99.00 |
| 240.830 | shot start | s0027 | CAM-05 | 74.67 |
| 241.780 | overlay onset | s0027 | HI-01 | 75.77 |
| 242.615 | shot middle | s0027 | CAM-05 | 77.64 |
| 243.015 | overlay middle | s0027 | HI-01 | 86.78 |
| 244.500 | shot start | s0028 | STATIC-01 | 99.00 |
| 250.055 | shot middle | s0028 | STATIC-01 | 99.00 |
| 255.710 | shot start | s0029 | CAM-05 | 99.00 |
| 257.070 | overlay onset | s0029 | AN-01 | 99.00 |
| 257.120 | overlay onset | s0029 | X-ANN-01 | 99.00 |
| 258.320 | overlay middle | s0029 | AN-01 | 99.00 |
| 258.520 | overlay middle | s0029 | X-ANN-01 | 99.00 |
| 260.135 | shot middle | s0029 | CAM-05 | 99.00 |
| 264.660 | shot start | s0030 | X-LAY-01 | 99.00 |
| 265.410 | overlay onset | s0030 | X-ANN-02 | 99.00 |
| 266.810 | overlay middle | s0030 | X-ANN-02 | 80.48 |
| 269.235 | shot middle | s0030 | X-LAY-01 | 91.82 |
| 273.910 | shot start | s0031 | CAM-05 | 99.00 |
| 281.470 | shot middle | s0031 | CAM-05 | 99.00 |
| 289.130 | shot start | s0032 | CAM-03 | 99.00 |
| 292.710 | shot middle | s0032 | CAM-03 | 99.00 |
| 296.390 | shot start | s0033 | X-CARD-01 | 99.00 |
| 296.940 | card | s0033 | X-CARD-01 FASHIONS AND FABRICS | 99.00 |
| 297.740 | shot middle | s0033 | X-CARD-01 | 99.00 |
| 298.240 | card (text gone) | s0033 | X-CARD-01 | 99.00 |
| 299.190 | shot start | s0034 | X-LAY-01 | 73.24 |
| 299.940 | overlay onset | s0034 | X-ANN-02 | 76.41 |
| 301.140 | shot middle | s0034 | X-LAY-01 | 77.95 |
| 301.340 | overlay middle | s0034 | X-ANN-02 | 80.16 |
| 303.190 | shot start | s0035 | CAM-01 | 99.00 |
| 308.510 | overlay onset | s0035 | X-ANN-01 | 71.67 |
| 309.910 | overlay middle | s0035 | X-ANN-01 | 74.69 |
| 312.535 | shot middle | s0035 | CAM-01 | 73.68 |
| 321.980 | shot start | s0036 | CAM-04 | 99.00 |
| 329.265 | shot middle | s0036 | CAM-04 | 99.00 |
| 336.650 | shot start | s0037 | CAM-05 | 99.00 |
| 337.340 | overlay onset | s0037 | X-ANN-01 | 99.00 |
| 338.740 | overlay middle | s0037 | X-ANN-01 | 99.00 |
| 343.785 | shot middle | s0037 | CAM-05 | 99.00 |
| 351.020 | shot start | s0038 | CAM-05 | 99.00 |
| 358.555 | shot middle | s0038 | CAM-05 | 99.00 |
| 360.870 | overlay onset | s0038 | X-ANN-01 | 99.00 |
| 362.270 | overlay middle | s0038 | X-ANN-01 | 99.00 |
| 366.190 | shot start | s0039 | CAM-05 | 99.00 |
| 370.375 | shot middle | s0039 | CAM-05 | 99.00 |
| 374.660 | shot start | s0040 | STATIC-01 | 99.00 |
| 375.390 | overlay onset | s0040 | X-ANN-01 | 99.00 |
| 376.790 | overlay middle | s0040 | X-ANN-01 | 99.00 |
| 376.890 | shot middle | s0040 | STATIC-01 | 99.00 |
| 379.220 | shot start | s0041 | STATIC-01 | 99.00 |
| 379.730 | overlay onset | s0041 | X-ANN-01 | 99.00 |
| 381.130 | overlay middle | s0041 | X-ANN-01 | 99.00 |
| 384.450 | shot middle | s0041 | STATIC-01 | 99.00 |
| 389.780 | shot start | s0042 | CAM-05 | 99.00 |
| 392.705 | shot middle | s0042 | CAM-05 | 99.00 |
| 395.730 | shot start | s0043 | STATIC-01 | 99.00 |
| 399.745 | shot middle | s0043 | STATIC-01 | 99.00 |
| 399.900 | overlay onset | s0043 | HI-01 | 99.00 |
| 400.020 | overlay onset | s0043 | X-ANN-01 | 99.00 |
| 401.420 | overlay middle | s0043 | X-ANN-01 | 99.00 |
| 401.755 | overlay middle | s0043 | HI-01 | 99.00 |
| 403.860 | shot start | s0044 | CAM-03 | 99.00 |
| 409.155 | shot middle | s0044 | CAM-03 | 74.38 |
| 414.550 | shot start | s0045 | X-CARD-01 | 99.00 |
| 415.100 | card | s0045 | X-CARD-01 THE ROOM | 99.00 |
| 415.900 | shot middle | s0045 | X-CARD-01 | 99.00 |
| 416.400 | card (text gone) | s0045 | X-CARD-01 | 99.00 |
| 417.350 | shot start | s0046 | STATIC-01 | 99.00 |
| 423.370 | shot middle | s0046 | STATIC-01 | 99.00 |
| 429.490 | shot start | s0047 | CAM-04 | 99.00 |
| 430.120 | overlay onset | s0047 | X-ANN-01 | 99.00 |
| 431.520 | overlay middle | s0047 | X-ANN-01 | 99.00 |
| 433.330 | shot middle | s0047 | CAM-04 | 99.00 |
| 437.270 | shot start | s0048 | STATIC-01 | 99.00 |
| 437.720 | overlay onset | s0048 | HI-01 | 99.00 |
| 439.220 | shot middle | s0048 | STATIC-01 | 99.00 |
| 439.270 | overlay middle | s0048 | HI-01 | 99.00 |
| 441.270 | shot start | s0049 | CAM-04 | 99.00 |
| 445.010 | shot middle | s0049 | CAM-04 | 99.00 |
| 448.850 | shot start | s0050 | CAM-05 | 99.00 |
| 451.740 | overlay onset | s0050 | X-ANN-01 | 99.00 |
| 453.140 | overlay middle | s0050 | X-ANN-01 | 99.00 |
| 459.280 | shot middle | s0050 | CAM-05 | 99.00 |
| 462.940 | overlay onset | s0050 | AN-01 | 99.00 |
| 464.190 | overlay middle | s0050 | AN-01 | 99.00 |
| 469.810 | shot start | s0051 | CAM-05 | 99.00 |
| 476.480 | shot middle | s0051 | CAM-05 | 99.00 |
| 476.590 | overlay onset | s0051 | X-ANN-01 | 99.00 |
| 477.990 | overlay middle | s0051 | X-ANN-01 | 99.00 |
| 479.680 | overlay onset | s0051 | AN-01 | 99.00 |
| 480.930 | overlay middle | s0051 | AN-01 | 99.00 |
| 483.250 | shot start | s0052 | CAM-05 | 99.00 |
| 491.520 | overlay onset | s0052 | X-ANN-01 | 99.00 |
| 492.560 | shot middle | s0052 | CAM-05 | 99.00 |
| 492.920 | overlay middle | s0052 | X-ANN-01 | 99.00 |
| 501.970 | shot start | s0053 | LAY-01 | 78.13 |
| 509.150 | shot middle | s0053 | LAY-01 | 72.20 |
| 516.430 | shot start | s0054 | CAM-05 | 99.00 |
| 518.400 | overlay onset | s0054 | X-ANN-01 | 99.00 |
| 519.800 | overlay middle | s0054 | X-ANN-01 | 99.00 |
| 523.915 | shot middle | s0054 | CAM-05 | 99.00 |
| 531.500 | shot start | s0055 | CAM-04 | 99.00 |
| 537.320 | shot middle | s0055 | CAM-04 | 99.00 |
| 537.610 | overlay onset | s0055 | AN-01 | 99.00 |
| 537.660 | overlay onset | s0055 | X-ANN-01 | 99.00 |
| 539.060 | overlay middle | s0055 | X-ANN-01 | 99.00 |
| 539.360 | overlay middle | s0055 | AN-01 | 99.00 |
| 543.240 | shot start | s0056 | CAM-05 | 99.00 |
| 544.320 | overlay onset | s0056 | AN-01 | 99.00 |
| 546.270 | overlay middle | s0056 | AN-01 | 99.00 |
| 548.980 | shot middle | s0056 | CAM-05 | 99.00 |
| 554.820 | shot start | s0057 | X-CARD-01 | 99.00 |
| 555.370 | card | s0057 | X-CARD-01 THE MIRROR | 99.00 |
| 556.170 | shot middle | s0057 | X-CARD-01 | 99.00 |
| 556.670 | card (text gone) | s0057 | X-CARD-01 | 99.00 |
| 557.620 | shot start | s0058 | CAM-05 | 56.93 |
| 561.940 | overlay onset | s0058 | HI-01 | 74.72 |
| 565.100 | shot middle | s0058 | CAM-05 | 80.69 |
| 567.185 | overlay middle | s0058 | HI-01 | 88.07 |
| 572.680 | shot start | s0059 | X-LAY-01 | 72.16 |
| 573.430 | overlay onset | s0059 | X-ANN-02 | 69.88 |
| 574.630 | shot middle | s0059 | X-LAY-01 | 68.91 |
| 574.830 | overlay middle | s0059 | X-ANN-02 | 71.99 |
| 576.680 | shot start | s0060 | DIA-07 | 99.00 |
| 579.880 | shot middle | s0060 | DIA-07 | 99.00 |
| 583.180 | shot start | s0061 | CAM-05 | 99.00 |
| 584.490 | overlay onset | s0061 | X-ANN-01 | 87.54 |
| 585.890 | overlay middle | s0061 | X-ANN-01 | 99.00 |
| 593.110 | shot middle | s0061 | CAM-05 | 99.00 |
| 603.140 | shot start | s0062 | CAM-03 | 99.00 |
| 608.405 | shot middle | s0062 | CAM-03 | 99.00 |
| 613.770 | shot start | s0063 | STATIC-01 | 99.00 |
| 616.670 | overlay onset | s0063 | AN-01 | 99.00 |
| 616.720 | overlay onset | s0063 | X-ANN-01 | 99.00 |
| 618.120 | overlay middle | s0063 | X-ANN-01 | 99.00 |
| 618.220 | overlay middle | s0063 | AN-01 | 99.00 |
| 620.855 | shot middle | s0063 | STATIC-01 | 99.00 |
| 628.040 | shot start | s0064 | CAM-05 | 99.00 |
| 634.230 | overlay onset | s0064 | HI-01 | 99.00 |
| 635.905 | shot middle | s0064 | CAM-05 | 99.00 |
| 638.875 | overlay middle | s0064 | HI-01 | 99.00 |
| 643.870 | shot start | s0065 | CAM-05 | 99.00 |
| 645.860 | overlay onset | s0065 | X-ANN-01 | 99.00 |
| 647.260 | overlay middle | s0065 | X-ANN-01 | 99.00 |
| 649.820 | overlay onset | s0065 | AN-01 | 99.00 |
| 651.570 | overlay middle | s0065 | AN-01 | 99.00 |
| 651.920 | overlay onset | s0065 | AN-01 | 99.00 |
| 653.670 | overlay middle | s0065 | AN-01 | 99.00 |
| 655.130 | shot middle | s0065 | CAM-05 | 99.00 |
| 666.490 | shot start | s0066 | X-CARD-01 | 99.00 |
| 667.040 | card | s0066 | X-CARD-01 THE ALCHEMIST | 99.00 |
| 667.840 | shot middle | s0066 | X-CARD-01 | 99.00 |
| 668.340 | card (text gone) | s0066 | X-CARD-01 | 99.00 |
| 669.290 | shot start | s0067 | STATIC-01 | 99.00 |
| 673.760 | shot middle | s0067 | STATIC-01 | 99.00 |
| 678.330 | shot start | s0068 | CAM-05 | 99.00 |
| 679.430 | shot middle | s0068 | CAM-05 | 99.00 |
| 680.630 | shot start | s0069 | STATIC-01 | 99.00 |
| 681.740 | overlay onset | s0069 | HI-01 | 99.00 |
| 682.050 | shot middle | s0069 | STATIC-01 | 99.00 |
| 682.480 | overlay middle | s0069 | HI-01 | 99.00 |
| 683.570 | shot start | s0070 | CAM-05 | 99.00 |
| 687.690 | shot middle | s0070 | CAM-05 | 99.00 |
| 691.910 | shot start | s0071 | CAM-05 | 99.00 |
| 697.270 | overlay onset | s0071 | HI-01 | 99.00 |
| 697.390 | overlay onset | s0071 | X-ANN-01 | 99.00 |
| 697.820 | shot middle | s0071 | CAM-05 | 99.00 |
| 698.790 | overlay middle | s0071 | X-ANN-01 | 99.00 |
| 700.425 | overlay middle | s0071 | HI-01 | 99.00 |
| 703.830 | shot start | s0072 | STATIC-01 | 99.00 |
| 703.980 | overlay onset | s0072 | HI-01 | 99.00 |
| 710.160 | overlay middle | s0072 | HI-01 | 99.00 |
| 710.260 | shot middle | s0072 | STATIC-01 | 99.00 |
| 716.790 | shot start | s0073 | CAM-05 | 99.00 |
| 722.775 | shot middle | s0073 | CAM-05 | 99.00 |
| 728.860 | shot start | s0074 | X-LAY-01 | 79.08 |
| 729.610 | overlay onset | s0074 | X-ANN-02 | 81.99 |
| 730.810 | shot middle | s0074 | X-LAY-01 | 80.36 |
| 731.010 | overlay middle | s0074 | X-ANN-02 | 79.07 |
| 732.860 | shot start | s0075 | STATIC-01 | 99.00 |
| 735.905 | shot middle | s0075 | STATIC-01 | 99.00 |
| 739.050 | shot start | s0076 | CAM-05 | 99.00 |
| 742.470 | shot middle | s0076 | CAM-05 | 99.00 |
| 745.990 | shot start | s0077 | CAM-05 | 99.00 |
| 751.025 | shot middle | s0077 | CAM-05 | 99.00 |
| 756.160 | shot start | s0078 | CAM-05 | 99.00 |
| 757.865 | shot middle | s0078 | CAM-05 | 99.00 |
| 759.670 | shot start | s0079 | STATIC-01 | 99.00 |
| 764.455 | shot middle | s0079 | STATIC-01 | 99.00 |
| 769.340 | shot start | s0080 | X-LAY-01 | 76.07 |
| 770.090 | overlay onset | s0080 | X-ANN-02 | 77.50 |
| 771.490 | overlay middle | s0080 | X-ANN-02 | 76.17 |
| 771.720 | shot middle | s0080 | X-LAY-01 | 79.71 |
| 774.200 | shot start | s0081 | X-LAY-01 | 99.00 |
| 774.950 | overlay onset | s0081 | X-ANN-02 | 99.00 |
| 776.350 | overlay middle | s0081 | X-ANN-02 | 99.00 |
| 777.840 | shot middle | s0081 | X-LAY-01 | 99.00 |
| 781.580 | shot start | s0082 | CAM-03 | 99.00 |
| 800.460 | overlay onset | s0082 | X-ANN-03 | 77.40 |
| 801.182 | shot middle | s0082 | CAM-03 | 74.91 |
| 801.340 | overlay onset | s0082 | X-ANN-03 | 74.75 |
| 802.380 | overlay onset | s0082 | X-ANN-03 | 78.72 |
| 803.220 | overlay onset | s0082 | X-ANN-03 | 74.46 |
| 803.510 | overlay middle | s0082 | X-ANN-03 | 77.86 |
| 804.140 | overlay middle | s0082 | X-ANN-03 | 78.53 |
| 804.930 | overlay middle | s0082 | X-ANN-03 | 74.56 |
| 805.520 | overlay middle | s0082 | X-ANN-03 | 74.57 |
| 819.833 | end fade | s0082 | fade | 82.08 |
| 820.783 | end fade | s0082 | fade | 99.00 |
