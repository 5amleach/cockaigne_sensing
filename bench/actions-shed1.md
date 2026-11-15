# Actions model bench, shed1

275 stills, a person found in 275. Crops padded by 0.25 and shrunk to 448 px, as live.

## objects
right 136 of 275 (49%); no answer 0; median 0.01 s, slowest tenth above 0.02 s
- by action: none 110/110 (100%); phone 18/55 (32%); drink 8/55 (14%); eat 0/55 (0%)
- by facing: facing the camera 58/100 (58%); side on to the camera 48/100 (48%); back to the camera 30/75 (40%)
- by mark: near mark 37/75 (49%); middle mark 64/125 (51%); far mark 35/75 (46%)
- by posture: standing 107/225 (47%); sitting 29/50 (58%)
- mistakes: eat called none 54; drink called none 46; phone called none 37; eat called drink 1; drink called phone 1

## qwen3-vl:4b-instruct
right 192 of 275 (69%); no answer 1; median 0.36 s, slowest tenth above 0.38 s
- by action: none 107/110 (97%); phone 41/55 (74%); drink 38/55 (69%); eat 6/55 (10%)
- by facing: facing the camera 81/100 (81%); side on to the camera 80/100 (80%); back to the camera 31/75 (41%)
- by mark: near mark 52/75 (69%); middle mark 89/125 (71%); far mark 51/75 (68%)
- by posture: standing 150/225 (66%); sitting 42/50 (84%)
- mistakes: eat called none 27; phone called none 14; drink called none 13; eat called drink 12; eat called phone 9; drink called phone 4; none called phone 2; none called eat 1

## gemma4:e2b
right 121 of 275 (44%); no answer 0; median 0.11 s, slowest tenth above 0.14 s
- by action: none 109/110 (99%); phone 11/55 (20%); drink 1/55 (1%); eat 0/55 (0%)
- by facing: facing the camera 52/100 (52%); side on to the camera 40/100 (40%); back to the camera 29/75 (38%)
- by mark: near mark 30/75 (40%); middle mark 56/125 (44%); far mark 35/75 (46%)
- by posture: standing 95/225 (42%); sitting 26/50 (52%)
- mistakes: drink called none 54; eat called none 50; phone called none 44; eat called drink 5; none called phone 1

## gemma3:4b
right 171 of 275 (62%); no answer 0; median 0.41 s, slowest tenth above 0.44 s
- by action: none 106/110 (96%); phone 38/55 (69%); drink 26/55 (47%); eat 1/55 (1%)
- by facing: facing the camera 74/100 (74%); side on to the camera 66/100 (66%); back to the camera 31/75 (41%)
- by mark: near mark 51/75 (68%); middle mark 77/125 (61%); far mark 43/75 (57%)
- by posture: standing 135/225 (60%); sitting 36/50 (72%)
- mistakes: eat called none 28; drink called none 25; eat called drink 18; phone called none 17; eat called phone 8; drink called phone 4; none called phone 4

## qwen2.5vl:3b
right 86 of 275 (31%); no answer 117; median 0.34 s, slowest tenth above 0.38 s
- by action: none 54/110 (49%); phone 20/55 (36%); drink 12/55 (21%); eat 0/55 (0%)
- by facing: facing the camera 40/100 (40%); side on to the camera 25/100 (25%); back to the camera 21/75 (28%)
- by mark: near mark 45/75 (60%); middle mark 33/125 (26%); far mark 8/75 (10%)
- by posture: standing 86/225 (38%); sitting 0/50 (0%)
- mistakes: eat called none 27; drink called none 17; phone called none 11; none called drink 6; none called phone 5; eat called phone 2; phone called drink 2; eat called drink 1; drink called phone 1

## moondream
right 84 of 275 (30%); no answer 0; median 0.14 s, slowest tenth above 0.16 s
- by action: none 0/110 (0%); phone 47/55 (85%); drink 37/55 (67%); eat 0/55 (0%)
- by facing: facing the camera 34/100 (34%); side on to the camera 35/100 (35%); back to the camera 15/75 (20%)
- by mark: near mark 25/75 (33%); middle mark 42/125 (33%); far mark 17/75 (22%)
- by posture: standing 64/225 (28%); sitting 20/50 (40%)
- mistakes: none called phone 94; eat called phone 33; eat called drink 22; drink called phone 18; none called drink 16; phone called drink 8
