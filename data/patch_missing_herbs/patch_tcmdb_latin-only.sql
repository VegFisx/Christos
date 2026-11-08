-- 推荐子集：只导**有拉丁学名**的 31 味（成分可走「药典拉丁学名→COCONUT 物种」）
-- ★ 应用前先备份 tcm.db；herb_id 用 PATCH 前缀
BEGIN TRANSACTION;
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0001', '南板蓝根', 'Baphicacanthus cusia', '的干燥根茎', '清热解毒，凉血消斑。用于温疫时毒，发热咽痛，温毒发斑，丹毒。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0002', '哈蟆油', 'Rana dybowskii', '', '补肾益精，养阴润肺。用于病后体弱，神疲乏力，心悸失眠，盗汗，痨嗽咳血。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0003', '大皂角', 'Gleditsia sinensis', '的干燥成熟果实', '祛痰开窍，散结消肿。用于中风口噤，昏迷不醒，癫痫痰盛，关窍不通，喉痹痰阻，顽痰喘咳，咳痰不爽，大便燥结；外治痈肿。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0004', '小驳骨', 'Gendarussa vulgaris', '的干燥地上部分', '祛瘀止痛，续筋接骨。用于跌打损伤，筋伤骨折，风湿骨痛，血瘀经闭，产后腹痛。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0005', '山银花', 'Lonicera macranthoides', '的干燥花', '清热解毒，疏散风热。用于痈肿疔疮，喉痹，丹毒，热毒血痢，风热感冒，温病发热。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0006', '山香圆叶', 'Turpinia arguta', '的干燥叶', '清热解毒，利咽消肿，活血止痛。用于乳蛾喉痹，咽喉肿痛，疮疡肿毒，跌扑伤痛。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0007', '广东紫珠', 'Callicarpa kwangtungensis', '的干燥茎', '收敛止血，散瘀，清热解毒。用于衄血，咯血，吐血，便血，崩漏，外伤出血，肺热咳嗽，咽喉肿痛，热毒疮疡，水火烫伤。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0008', '广金钱草', 'Desmodium styracifolium', '的干燥地上部分', '利湿退黄，利尿通淋。用于黄疸尿赤，热淋，石淋，小便涩痛，水肿尿少。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0009', '暴马子皮', 'Syringa reticulata', '的干燥干皮', '清肺祛痰，止咳平喘。用于咳喘痰多。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0010', '木芙蓉叶', 'Hibiscus mutabilis', '的干燥叶', '凉血，解毒，消肿，止痛。用于痈疽焮肿，缠身蛇丹，烫伤，目赤肿痛，跌打损伤。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0011', '杠板归', 'Polygonum perfoliatum', '的干燥地上部分', '清热解毒，利水消肿，止咳。用于咽喉肿痛，肺热咳嗽，小儿顿咳，水肿尿少，湿热泻痢，湿疹，疖肿，蛇虫咬伤。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0012', '榼藤子', 'Entada phaseoloides', '的干燥成熟种子', '补气补血，健胃消食，除风止痛，强筋硬骨。用于水血不足，面色苍白，四肢无力，脘腹疼痛，纳呆食少；风湿肢体关节痿软疼痛，性冷淡。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0013', '油松节', 'Pinus tabuliformis', '', '祛风除湿，通络止痛。用于风寒湿痹，历节风痛，转筋挛急，跌打伤痛。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0014', '滇鸡血藤', 'Kadsura interior', '的干燥藤茎', '活血补血，调经止痛，舒筋通络。用于月经不调，痛经，麻木瘫痪，风湿痹痛，气血虚弱。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0015', '瓜子金', 'Polygala japonica', '的干燥全草', '祛痰止咳，活血消肿，解毒止痛。用于咳嗽痰多，咽喉肿痛；外治跌打损伤，疔疮疖肿，蛇虫咬伤。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0016', '紫珠叶', 'Callicarpa formosana', '的干燥叶', '凉血收敛止血，散瘀解毒消肿。用于衄血，咯血，吐血，便血，崩漏，外伤出血，热毒疮疡，水火烫伤。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0017', '紫萁贯众', 'Osmunda japonica', '的干燥根茎', '清热解毒，止血，杀虫。用于疫毒感冒，热毒泻痢，痈疮肿毒，吐血，衄血，便血，崩漏，虫积腹痛。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0018', '翼首草', 'Pterocephalus hookeri', '的干燥全草', '解毒除瘟，清热止痢，祛风通痹。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0019', '臭灵丹草', 'Laggera pterodonta', '的干燥地上部分', '清热解毒，止咳祛痰。用于风热感冒，咽喉肿痛，肺热咳嗽。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0020', '蓍草', 'Achillea alpina', '的干燥地上部分', '解毒利湿，活血止痛。用于乳蛾咽痛，泄泻痢疾，肠痈腹痛，热淋涩痛，湿热带下，蛇虫咬伤。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0021', '蓝布正', 'Geum aleppicum', '的干燥全草', '益气健脾，补血养阴，润肺化痰。用于气血不足，虚痨咳嗽，脾虚带下。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0022', '藏菖蒲', 'Acorus calamus', '的干燥根茎', '温胃，消炎止痛。用于补胃阳，消化不良，食物积滞，白喉，炭疽等。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0023', '裸花紫珠', 'Callicarpa nudiflora', '的干燥叶', '消炎，解肿毒，化湿浊，止血。用于细菌性感染引起炎症肿毒，急性传染性肝炎，内外伤出血。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0024', '西瓜霜', 'Citrullus lanatus', '', '清热泻火，消肿止痛。用于咽喉肿痛，喉痹，口疮。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0025', '西青果', 'Terminalia chebula', '', '清热生津，解毒。用于阴虚白喉。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0026', '野马追', 'Eupatorium lindleyanum', '的干燥地上部分', '化痰止咳平喘。用于痰多咳嗽气喘。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0027', '金果榄', 'Tinospora sagittata', '的干燥块根', '清热解毒，利咽，止痛。用于咽喉肿痛，痈疽疔毒，泄泻，痢疾，脘腹疼痛。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0028', '金龙胆草', 'Conyza blinii', '的干燥地上部分', '清热化痰，止咳平喘，解毒利湿，凉血止血。用于肺热咳嗽，痰多气喘，咽痛，口疮，湿热黄疸，衄血，便血，崩漏，外伤出血。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0029', '飞扬草', 'Euphorbia hirta', '的干燥全草', '清热解毒，利湿止痒，通乳。用于肺痈，乳痈，疔疮肿毒，牙疳，痢疾，泄泻，热淋，血尿，湿疹，脚癣，皮肤瘙痒，产后少乳。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0030', '黄藤', 'Fibraurea recisa', '的干燥藤茎', '清热解毒，泻火通便。用于热毒内盛，便秘，泻痢，咽喉肿痛，目赤红肿，痈肿疮毒。', 'chemreact补丁(有拉丁):药典2025一部');
INSERT INTO herbs (herb_id, name_cn, latin, use_part, function, alias) VALUES ('PATCHL0031', '黑种草子', 'Nigella glandulifera', '的干燥成熟种子', '补肾健脑，通经，通乳，利尿。用于耳鸣健忘，经闭乳少，热淋，石淋。', 'chemreact补丁(有拉丁):药典2025一部');
COMMIT;

