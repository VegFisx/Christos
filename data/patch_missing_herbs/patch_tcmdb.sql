-- chemreact 补库补丁（药典缺 52 味）：herb 元数据
-- ★ 应用前请先备份 tcm.db；本文件由 tools\build_missing_herbs_patch.py 生成
-- ★ 本补丁**不含成分数据**：成分仍走软件自带的「药典拉丁学名 → COCONUT 物种」兜底
BEGIN TRANSACTION;
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00001', '亚乎奴(锡生藤)', NULL, NULL, NULL, 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00002', '体外培育牛黄', NULL, NULL, '清心，豁痰，开窍，凉肝，息风，解毒。用于热病神昏，中风痰迷，惊痫抽搐，癫痫发狂，咽喉肿痛，口舌生疮，痈肿疔疮。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00003', '冰片(合成龙脑)', NULL, NULL, NULL, 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00004', '制何首乌', NULL, NULL, '补肝肾，益精血，乌须发，强筋骨，化浊降脂。用于血虚萎黄，眩晕耳鸣，须发早白，腰膝酸软，肢体麻木，崩漏带下，高脂血症。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00005', '制天南星', NULL, NULL, '燥湿化痰，祛风止痉，散结消肿。用于顽痰咳嗽，风痰眩晕，中风痰壅，口眼㖞斜，半身不遂，癫痫，惊风，破伤风；外用治痈肿，蛇虫咬伤。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00006', '南板蓝根', 'Baphicacanthus cusia', '的干燥根茎', '清热解毒，凉血消斑。用于温疫时毒，发热咽痛，温毒发斑，丹毒。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00007', '哈蟆油', 'Rana dybowskii', NULL, '补肾益精，养阴润肺。用于病后体弱，神疲乏力，心悸失眠，盗汗，痨嗽咳血。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00008', '土鳖虫(䗪虫)', NULL, NULL, NULL, 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00009', '大皂角', 'Gleditsia sinensis', '的干燥成熟果实', '祛痰开窍，散结消肿。用于中风口噤，昏迷不醒，癫痫痰盛，关窍不通，喉痹痰阻，顽痰喘咳，咳痰不爽，大便燥结；外治痈肿。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00010', '大蓟炭', NULL, NULL, '凉血止血。用于衄血，吐血，尿血，便血，崩漏，外伤出血。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00011', '天然冰片(右旋龙脑)', NULL, NULL, NULL, 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00012', '姜半夏', NULL, NULL, '温中化痰，降逆止呕。用于痰饮呕吐，胃脘痞满。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00013', '小驳骨', 'Gendarussa vulgaris', '的干燥地上部分', '祛瘀止痛，续筋接骨。用于跌打损伤，筋伤骨折，风湿骨痛，血瘀经闭，产后腹痛。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00014', '山银花', 'Lonicera macranthoides', '的干燥花', '清热解毒，疏散风热。用于痈肿疔疮，喉痹，丹毒，热毒血痢，风热感冒，温病发热。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00015', '山香圆叶', 'Turpinia arguta', '的干燥叶', '清热解毒，利咽消肿，活血止痛。用于乳蛾喉痹，咽喉肿痛，疮疡肿毒，跌扑伤痛。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00016', '广东紫珠', 'Callicarpa kwangtungensis', '的干燥茎', '收敛止血，散瘀，清热解毒。用于衄血，咯血，吐血，便血，崩漏，外伤出血，肺热咳嗽，咽喉肿痛，热毒疮疡，水火烫伤。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00017', '广金钱草', 'Desmodium styracifolium', '的干燥地上部分', '利湿退黄，利尿通淋。用于黄疸尿赤，热淋，石淋，小便涩痛，水肿尿少。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00018', '延胡索(元胡)', NULL, NULL, NULL, 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00019', '暴马子皮', 'Syringa reticulata', '的干燥干皮', '清肺祛痰，止咳平喘。用于咳喘痰多。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00020', '木芙蓉叶', 'Hibiscus mutabilis', '的干燥叶', '凉血，解毒，消肿，止痛。用于痈疽焮肿，缠身蛇丹，烫伤，目赤肿痛，跌打损伤。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00021', '杠板归', 'Polygonum perfoliatum', '的干燥地上部分', '清热解毒，利水消肿，止咳。用于咽喉肿痛，肺热咳嗽，小儿顿咳，水肿尿少，湿热泻痢，湿疹，疖肿，蛇虫咬伤。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00022', '榼藤子', 'Entada phaseoloides', '的干燥成熟种子', '补气补血，健胃消食，除风止痛，强筋硬骨。用于水血不足，面色苍白，四肢无力，脘腹疼痛，纳呆食少；风湿肢体关节痿软疼痛，性冷淡。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00023', '油松节', 'Pinus tabuliformis', NULL, '祛风除湿，通络止痛。用于风寒湿痹，历节风痛，转筋挛急，跌打伤痛。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00024', '清半夏', NULL, NULL, '燥湿化痰。用于湿痰咳嗽，胃脘痞满，痰涎凝聚，咯吐不出。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00025', '滇鸡血藤', 'Kadsura interior', '的干燥藤茎', '活血补血，调经止痛，舒筋通络。用于月经不调，痛经，麻木瘫痪，风湿痹痛，气血虚弱。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00026', '灯盏细辛(灯盏花)', NULL, NULL, NULL, 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00027', '炒瓜蒌子', NULL, NULL, '润肺化痰，滑肠通便。用于燥咳痰黏，肠燥便秘。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00028', '猪胆粉', NULL, NULL, '清热润燥，止咳平喘，解毒。用于顿咳，哮喘，热病燥渴，目赤，喉痹，黄疸，泄泻，痢疾，便秘，痈疮肿毒。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00029', '瓜子金', 'Polygala japonica', '的干燥全草', '祛痰止咳，活血消肿，解毒止痛。用于咳嗽痰多，咽喉肿痛；外治跌打损伤，疔疮疖肿，蛇虫咬伤。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00030', '皂矾(绿矾)', NULL, NULL, NULL, 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00031', '紫珠叶', 'Callicarpa formosana', '的干燥叶', '凉血收敛止血，散瘀解毒消肿。用于衄血，咯血，吐血，便血，崩漏，外伤出血，热毒疮疡，水火烫伤。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00032', '紫萁贯众', 'Osmunda japonica', '的干燥根茎', '清热解毒，止血，杀虫。用于疫毒感冒，热毒泻痢，痈疮肿毒，吐血，衄血，便血，崩漏，虫积腹痛。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00033', '绵马贯众炭', NULL, NULL, '收涩止血。用于崩漏下血。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00034', '翼首草', 'Pterocephalus hookeri', '的干燥全草', '解毒除瘟，清热止痢，祛风通痹。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00035', '臭灵丹草', 'Laggera pterodonta', '的干燥地上部分', '清热解毒，止咳祛痰。用于风热感冒，咽喉肿痛，肺热咳嗽。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00036', '艾片(左旋龙脑)', NULL, NULL, NULL, 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00037', '荆芥炭', NULL, NULL, '收敛止血。用于便血，崩漏，产后血晕。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00038', '荆芥穗炭', NULL, NULL, '收涩止血。用于便血，崩漏，产后血晕。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00039', '蓍草', 'Achillea alpina', '的干燥地上部分', '解毒利湿，活血止痛。用于乳蛾咽痛，泄泻痢疾，肠痈腹痛，热淋涩痛，湿热带下，蛇虫咬伤。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00040', '蓝布正', 'Geum aleppicum', '的干燥全草', '益气健脾，补血养阴，润肺化痰。用于气血不足，虚痨咳嗽，脾虚带下。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00041', '藏菖蒲', 'Acorus calamus', '的干燥根茎', '温胃，消炎止痛。用于补胃阳，消化不良，食物积滞，白喉，炭疽等。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00042', '裸花紫珠', 'Callicarpa nudiflora', '的干燥叶', '消炎，解肿毒，化湿浊，止血。用于细菌性感染引起炎症肿毒，急性传染性肝炎，内外伤出血。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00043', '西瓜霜', 'Citrullus lanatus', NULL, '清热泻火，消肿止痛。用于咽喉肿痛，喉痹，口疮。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00044', '西青果', 'Terminalia chebula', NULL, '清热生津，解毒。用于阴虚白喉。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00045', '野马追', 'Eupatorium lindleyanum', '的干燥地上部分', '化痰止咳平喘。用于痰多咳嗽气喘。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00046', '金果榄', 'Tinospora sagittata', '的干燥块根', '清热解毒，利咽，止痛。用于咽喉肿痛，痈疽疔毒，泄泻，痢疾，脘腹疼痛。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00047', '金龙胆草', 'Conyza blinii', '的干燥地上部分', '清热化痰，止咳平喘，解毒利湿，凉血止血。用于肺热咳嗽，痰多气喘，咽痛，口疮，湿热黄疸，衄血，便血，崩漏，外伤出血。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00048', '飞扬草', 'Euphorbia hirta', '的干燥全草', '清热解毒，利湿止痒，通乳。用于肺痈，乳痈，疔疮肿毒，牙疳，痢疾，泄泻，热淋，血尿，湿疹，脚癣，皮肤瘙痒，产后少乳。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00049', '黄藤', 'Fibraurea recisa', '的干燥藤茎', '清热解毒，泻火通便。用于热毒内盛，便秘，泻痢，咽喉肿痛，目赤红肿，痈肿疮毒。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00050', '黑种草子', 'Nigella glandulifera', '的干燥成熟种子', '补肾健脑，通经，通乳，利尿。用于耳鸣健忘，经闭乳少，热淋，石淋。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00051', '龟甲胶', NULL, NULL, '滋阴，养血，止血。用于阴虚潮热，骨蒸盗汗，腰膝酸软，血虚萎黄，崩漏带下。', 'chemreact补丁:药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCH00052', '􀅰', NULL, NULL, NULL, 'chemreact补丁:药典2025一部');
COMMIT;

-- 核对：SELECT COUNT(*) FROM herbs WHERE herb_id LIKE 'PATCH%';  -- 期望 52
