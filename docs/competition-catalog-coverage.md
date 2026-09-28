# 学校赛事目录采集覆盖表

核查时间：2026-09-28 12:03（北京时间）。本文件是本机首轮实测快照，后续状态以后台为准。

范围依据为用户提供的《同济大学本科生学科竞赛目录（2026版）》，完整保留255项及全部学科。目录官方发布页：[学校通知](https://qdc.tongji.edu.cn/info/1035/1791.htm)。原附件中的负责人姓名和工号不进入仓库。

## 实测数量

| 项目 | 数量 |
| --- | ---: |
| 学校目录条目 | 255 |
| 已登记官方来源（含暂不启用） | 245 |
| 已启用自动检查 | 234 |
| 已登记但暂停采集 | 11 |
| 官方入口仍待确认 | 10 |
| 最近结果：读取失败 | 82 |
| 最近结果：部分读取成功 | 16 |
| 最近结果：仅入口快照 | 53 |
| 最近结果：读取成功 | 83 |
| 至少保存过一页的启用来源 | 152 |
| 启用来源保存的原文版本 | 290 |
| 当前页面版本：通知候选 / 入口快照 | 109 / 181 |
| 已发布且关联目录的赛事赛项 | 13 |
| 前台当前 / 历史赛事 | 11 / 2 |

**统计口径：**目录条目是赛事系列，公开卡片是具体届次或赛项，二者不能一一计数。同一官网可服务多个目录条目；原文按条目分开存档，因此页面数不是互联网唯一URL数。“读取成功”表示本轮有限页面获取成功，不代表获取完整、最新、正在报名或完成字段提取；“仅入口快照”表示未发现可继续跟进的匹配通知。通知候选也可能是公示或往届报道。已撤销的错误入口及其历史不计入上述启用来源原文数。

## 运行方式

学校目录 → 已核对官网/主办方 → 每6小时按到期时间检查 → 保存正文与版本 → 后台提取核验 → 正式赛事。浏览器读取已保存的正式赛事，不等待爬虫。整入口失败按12、24、48、72小时退避，最高72小时；动态页面、登录或附件限制保留真实失败状态，不绕过访问限制。

本轮没有调用AI。新监测原文只进后台；当前只有AIC与NCDA专用适配器可进入现有结构化采纳流程。任意官网的资格、人数、截止日期和报名链接尚不能自动可靠填满公开卡片。旧数维杯记录保留，默认公开列表及持续采集按学校目录排除它。

## 逐项来源

“依据”链接用于证明赛事归属；入口有时是往届官方通知或主办方列表，具体边界见最后一列。暂停、失败和待确认均不等于比赛取消。目录等级也不等于每个子赛奖项均按该等级认定。

| 编号 | 目录原名 | 等级 | 官方入口与依据 | 本机检查 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 2026001 | 中国国际大学生创新大赛（2026） | A+ | [主办／承办方](https://www.moe.gov.cn/srcsite/A08/s5672/202607/t20260731_1445670.html) | 仅入口快照 | 教育部2026通知；报名系统另行登录；监测公开通知即可。 |
| 2026002 | “挑战杯”中国大学生创业计划竞赛 | A+ | [赛事站](https://www.tiaozhanbei.net/) · [依据](https://old.tiaozhanbei.net/focus) | 读取成功 | 官方简介明确官网域名；2026为第十五届创业计划竞赛，勿与课外学术科技作品赛混用。 |
| 2026003 | 中国青年科技创新“揭榜挂帅”擂台赛 | A+ | [赛事站](https://www.tiaozhanbei.net/) · [依据](https://youth.cau.edu.cn/art/2026/5/15/art_45078_1113491.html) | 读取成功 | 2026校方通知指向挑战杯官网及2026.tiaozhanbei.net报名；报名需登录，公开通知可监测。 |
| 2026004 | 全国大学生金相技能大赛 | A | [赛事站](https://www.jxds.tech/tongzhi) | 部分读取成功：empty_or_javascript | 赛事专站通知页可公开检索，已出现2026通知；按通知核对具体届次。 |
| 2026005 | 全国大学生测绘学科创新创业智能大赛 | A | [主办／承办方](https://www.csgpc.org/detail/27739.html) | 读取成功 | 中国测绘学会2026二号通知；2026赛期已在7月底至8月初，不当作仍可报名。 |
| 2026006 | iCAN大学生创新创业大赛 | A | [赛事站](https://g-ican.com/) · [依据](https://due.xjtu.edu.cn/info/1172/9912.htm) | 读取失败：empty_or_javascript | 校方2026通知明确官网；站内多赛道须分别辨别截止。 |
| 2026007 | 全国大学生创新年会 | A | [赛事站](https://www.gjcxcy.cn/Index) | 读取成功 | 公开主页载2026第十九届年会通知；项目遴选不是普通竞赛直接报名。 |
| 2026008 | 全国大学生工程实践与创新能力大赛（2026） | A | [主办／承办方](https://gcxl.dlut.edu.cn/new/) · [依据](https://www.csust.edu.cn/jwc/info/1101/8143.htm) | 仅入口快照 | 组委会官网已转2027第十届；2026为部分校赛启动年份，不能直接把2027国赛规则改称2026，页面通知部分依赖JavaScript。 |
| 2026009 | 中国大学生机械工程创新创意大赛-智能制造赛 | A | [主办／承办方](https://www.cmes.org/notice/010c5f85554e440e99d702008b58a26f.html) | 读取成功 | 主办学会2026总通知含智能制造赛；须按赛项附件区分，不与西门子杯混为同赛事。 |
| 2026010 | “西门子杯”中国智能制造挑战赛 | A | [赛事站](https://www.siemenscup-cimc.org.cn/) · [依据](https://www.ad.siemens.com.cn/CNC4YOU/Home/ArticleContent/3077) | 读取成功 | 西门子官方资料佐证官网；站内有2026第二十届通知，多方向分别跟踪。 |
| 2026011 | VEX机器人全国精英赛 | A | [主办／承办方](https://news.sjtu.edu.cn/jdyw/20241231/206206.html) | 仅入口快照 | 实际打开主办上海交大2024-2025精英赛报道，正文明确含VEX U大学组及学生创新中心承办；确认赛事系列官方源，当前仅历史赛季，不假定2026报名开启。 |
| 2026012 | 大学生新一代信息通信科技大赛 | A | [赛事站](https://dtcup.dtxiaotangren.com/) | 读取失败：robots_unavailable | 官网明确原大唐杯更名为信科赛，现有2026通知；公开通知可读。 |
| 2026013 | 国际大学生智能农业装备创新大赛 | A | [主办／承办方](https://uiaec.ujs.edu.cn/index.php) · [依据](https://uiaec.ujs.edu.cn/news_show.php?id=234) | 读取失败：robots_unavailable | 江苏大学赛事官网；2026-09已发布第十二届通知，决赛进入2027，需区分年度。 |
| 2026014 | 华为ICT大赛 | A | [赛事站](https://www.huawei.com/minisite/ict-competition-2025-2026-global/cn/) · [依据](https://www.huawei.com/cn/news/2026/6/ict-competition-global) | 读取成功 | 华为官方2025—2026赛季已收官；新赛季需单独查通知，不视为仍开放报名。 |
| 2026015 | 全国大学生电子设计竞赛 | A | [主办／承办方](https://nuedc.xjtu.edu.cn/) · [依据](https://nuedc.sjtu.edu.cn/cn/show.aspx?flag=7&info_id=1306&info_lb=8) | 读取失败：robots_unavailable | 全国官网及承办专题赛官方通知；2026有不同专题赛，不混用国赛/省赛/专题赛期限。 |
| 2026016 | 全国大学生集成电路创新创业大赛 | A | [赛事站](https://www.ciciec.com/) | 读取失败：robots_unavailable | 全国大学生集成电路创新创业大赛公开官网，有2026通知。 |
| 2026017 | 全国大学生嵌入式芯片与系统设计竞赛 | A | [赛事站](https://www.socchina.net/home) · [依据](https://www.gowinsemi.com.cn/university/match2026) | 读取成功 | 公开官网与支持企业2026赛页佐证，芯片应用/设计赛道分别核对。 |
| 2026018 | 全国大学生物联网设计竞赛 | A | [主办／承办方](https://iot.sjtu.edu.cn/Default.aspx) · [依据](https://ieetc.shiep.edu.cn/35/0f/c6747a275727/page.htm) | 读取失败：empty_or_javascript | 上海交大赛事官网载2026通知；地区决赛与国赛不同阶段。 |
| 2026019 | 全国大学生智能汽车竞赛 | A | [赛事站](http://www.smartcarrace.com/) · [依据](https://due.xjtu.edu.cn/info/1172/9891.htm) | 读取失败：empty_or_javascript | 2026西安交大通知明确大赛官网；本次直取返回502，需运行时复查可用性。第21届与竞速/创意组规则应分别核实。 |
| 2026020 | 全球校园人工智能算法精英大赛 | A | [赛事站](https://www.aicomp.cn/tracks/tracks-5) · [依据](https://www.aicomp.cn/tracks/tracks-5/4924.html) | 读取成功 | 已核验并已有适配器；2026各主题赛独立，禁止混用deadline。 |
| 2026021 | 睿抗机器人开发者大赛（RAICOM） | A | [赛事站](https://www.raicom.com.cn/) · [依据](https://cxcyxy.ntu.edu.cn/2026/0430/c10412a290318/page.htm) | 读取成功 | 南通大学2026通知明确赛事官网，多赛道分别核对。 |
| 2026022 | 中国高校智能机器人创意大赛 | A | [赛事站](https://www.robotcontest.cn/home/homepage) | 读取失败：empty_or_javascript | 公开官网有2026第九届通知；具体赛道规程另查。 |
| 2026023 | 中国机器人大赛暨RoboCup机器人世界杯中国赛 | A | [赛事站](https://rcccaa.drct-caa.org.cn/) · [依据](https://www.caa.org.cn/article/191/6195.html) | 读取成功 | 中国自动化学会机器人竞赛与培训部2026通知站；RoboCup赛区与中国机器人大赛赛区时间不同，不能合并同一截止。 |
| 2026024 | 中国机器人及人工智能大赛 | A | [赛事站](https://www.caairobot.com/) | 读取成功 | 公开官网有2026第二十八届各省赛及决赛通知，勿将省赛等同全国截止。 |
| 2026025 | SAMPE 2026 Student Bridge Contest | A | [赛事站](https://www.sampeamerica.org/student-bridge-competition) | 仅入口快照 | SAMPE Conference美国站2026 Student Bridge规则；不要与中国第十八届机翼/桥梁竞赛合并。 |
| 2026026 | 第十八届SAMPE国际超轻复合材料桥梁/机翼学生竞赛 | A | [赛事站](https://www.sampechina.org/) · [依据](https://news.tongji.edu.cn/info/1003/95061.htm) | 读取失败：empty_or_javascript | SAMPE中国官网2026第十八届；同济官方新闻佐证本届已举行，官网About_Contest可能仍为2025旧版。 |
| 2026027 | 全国大学生化工设计竞赛 | A | [主办／承办方](https://iche.zju.edu.cn/) · [依据](https://scce.hainanu.edu.cn/info/1014/11533.htm) | 部分读取成功：empty_or_javascript | 浙江大学赛事专站及2026参赛通知；具体届次和赛区须按当期通知区分。 |
| 2026028 | 全国大学生化工实验大赛 | A | [赛事站](https://edu.cteic.com/match/app/main) | 读取失败：robots_unavailable | 主办中国化工教育协会，公开赛事平台；2026第九届资料可检索，系统功能可能需登录。 |
| 2026029 | 上海大学生化学实验竞赛暨实验创新设计竟赛 | A | [主办／承办方](https://chemlab.shu.edu.cn/info/1004/4152.htm) | 仅入口快照 | 承办上海大学2026第二轮通知，第二十届7月举行；后续换承办校需新确认。 |
| 2026030 | 全国大学生能源经济学术创意大赛 | A | [赛事站](http://energy.qibebt.ac.cn/eneco/contribution/) · [依据](https://ieep.upc.edu.cn/2025/1010/c15488a473002/page.htm) | 读取失败：robots_unavailable | 2026第十二届通知明确中科院官网及唯一报名系统；报名登录与公开通知区分，2026论文提交3月已结束。 本次公开入口返回空正文，需进一步适配。 |
| 2026031 | 全国三维数字化创新设计大赛 | A | [赛事站](https://3dds.3ddl.net/index.php?ctl=Informationlist&id=696&met=details) · [依据](https://sjxy.lsu.edu.cn/2026/0518/c3461a367781/page.htm) | 读取成功 | 2026第19届官方总通知；年度竞赛与精英联赛、青少年组各有入口和时间，不能混用。 |
| 2026032 | 一带一路暨金砖国家技能发展与技术创新大赛 | A | [赛事站](https://www.bricsfuture.org.cn/t/20.html) · [依据](https://www.bricsfuture.org.cn/a/20-296.html) | 读取失败：robots_unavailable | 金砖未来研究院赛事专栏及2026技术创新赛通知；赛项多，分别监测。 |
| 2026033 | 第二十五届全国大学生机器人大赛ROBOMASTER | A | [赛事站](https://www.robomaster.com/zh-CN) · [依据](https://www.robomaster.com/zh-CN/robo/rm?type=rm-info) | 仅入口快照 | RoboMaster官网有2026赛季；与ROBOCON分开记录，联赛/超级对抗赛区别。 |
| 2026034 | 第十二届全国大学生机械创新设计大赛 | A | [主办／承办方](https://12umic.hit.edu.cn/20012/list.htm) · [依据](https://12umic.hit.edu.cn/2026/0915/c20012a401561/page.htm) | 读取成功 | 已核验承办哈工大通知入口；近期数字孪生通知属2027阶段，不能当2026主赛初次报名。 |
| 2026035 | 第十九届全国大学生先进成图技术与产品信息建模创新大赛 | A | [赛事站](https://www.chengtudasai.com/) | 读取失败：robots_unavailable | 官网有2026第十九届首轮通知；公开通知可检索。 |
| 2026036 | 全国大学生节能减排社会实践与科技竞赛 | A | [赛事站](https://www.jienengjianpai.org/) · [依据](https://jienengjianpai.org/?lang=en) | 读取成功 | 官网已有2026第十九届结果，不将结果页当报名；公开历史与下一届分开。 |
| 2026037 | 中国大学生机械工程创新创意大赛-工业工程与精益管理创新赛 | A | [主办／承办方](https://www.cmes.org/notice/010c5f85554e440e99d702008b58a26f.html) | 读取成功 | 主办中国机械工程学会2026总通知明确工业工程与精益管理赛；按赛项附件区分。 |
| 2026038 | 中国大学生机械工程创新创意大赛-机械产品数字化设计赛 | A | [主办／承办方](https://www.cmes.org/notice/010c5f85554e440e99d702008b58a26f.html) | 读取成功 | 主办学会总通知及实施方案列机械产品数字化设计赛；不要混为其他机械赛项。 |
| 2026039 | 中国大学生机械工程创新创意大赛-物流技术创意赛 | A | [主办／承办方](https://www.cmes.org/notice/010c5f85554e440e99d702008b58a26f.html) | 读取成功 | 主办学会总通知列物流技术创意赛；与物流设计大赛不是同一赛事。 |
| 2026040 | “中国软件杯”大学生软件设计大赛 | A | [赛事站](https://www.cnsoftbei.com/) · [依据](https://qihang.hrbeu.edu.cn/2026/0531/c3223a349416/page.htm) | 读取成功 | 2026第十五届校方通知明确官网；本次直取502需运行时复查，不等同当前仍可报名。 |
| 2026041 | ACM-ICPC国际大学生程序设计竞赛 | A | [主办／承办方](https://icpc.pku.edu.cn/tzgg/) · [依据](https://icpc.pku.edu.cn/) | 部分读取成功：empty_or_javascript | ICPC北京总部公开通知，有2026Asia EC；区域赛、网络赛、全球赛不同阶段。 |
| 2026042 | 百度之星·程序设计大赛 | A | [赛事站](https://astar.baidu.com/) · [依据](https://www.jwc.ynu.edu.cn/info/1009/4331.htm) | 读取失败：robots_unavailable | 云南大学2026第二十二届通知明确官方入口；本次直取超时，不沿用2018/2019历史站规则。 |
| 2026043 | 全国大学生计算机系统能力大赛 | A | [赛事站](https://www.csc-he.cn/) · [依据](https://pra.educg.net/) | 仅入口快照 | 系统能力大赛公共主站，多方向含操作系统/CPU/编译/智能计算，分别核对。 |
| 2026044 | 全国大学生信息安全竞赛 | A | [赛事站](https://www.ciscn.cn/) | 读取失败：robots_unavailable | 官网2026第十九届作品赛；创新实践能力赛另有ccb.itsec.gov.cn，不混用规则。 |
| 2026045 | 全国大学生信息安全与对抗技术竞赛 | A | [赛事站](https://www.isclab.org.cn/category/iscc/iscc_3/) · [依据](https://www.isclab.org.cn/2026/03/16/2026年第23届信息安全与对抗技术竞赛通知/) | 读取成功 | 信息系统及安全对抗实验中心ISCC官方第23届2026；赛项举办日期不同，智能安全赛等须单独核实。 |
| 2026046 | 中国大学生服务外包创新创业大赛 | A | [赛事站](https://www.fwwb.org.cn/) · [依据](https://www.fwwb.org.cn/about/index) | 读取成功 | 主办赛站公开公告，2026第十七届；赛道分别核对。 |
| 2026047 | 中国大学生计算机设计大赛 | A | [主办／承办方](https://jsjds.blcu.edu.cn/) · [依据](https://jsjds.blcu.edu.cn/gyds1/csyq.htm) | 读取成功 | 官网与2026参赛要求已核验；国赛入围确认并非全体学生初次报名。 |
| 2026048 | 中国高校计算机大赛 | A | [赛事站](https://www.appcontest.net/) | 读取失败：empty_or_javascript | 确认的是C4移动应用创新分赛官网，2026第十一届；目录总项还含其他分赛，不能以此覆盖全部C4。 |
| 2026049 | 2026同济大学国际建造节 | A | [校内官方通知](https://caup.tongji.edu.cn/a2/c8/c33362a369352/page.htm) | 读取失败：robots_unavailable | 同济建筑城规学院2026启动通知；比赛6月6—7日，已过期。 |
| 2026050 | UIA 世界大学生建筑设计竞赛 | A | [赛事站](https://uia2026bcn.org/international-student-competition/) · [依据](https://www.uia-architectes.org/en/events/world-congresses-of-architects/barcelona-2026/) | 读取成功 | UIA国际建协官方指向2026巴塞罗那大会站学生赛，已有获奖公告；不能当当前可报名。 |
| 2026051 | UIA-霍普杯国际大学生建筑设计竞赛 | A | [赛事站](https://hypcup.uedmagazine.net/index.php?a=index&c=Lists&m=home&tid=39) · [依据](https://hypcup.uedmagazine.net/down/2024UIA.pdf) | 读取成功 | 主办赛事规程明确官网域名；当前网页为2026，旧PDF仅佐证域名不复用2024期限。 |
| 2026052 | WUPENICITY城市可持续调研报告国际竞赛（智慧低碳交通） | A | [赛事站](http://wupen.org/) · [依据](https://caup.tongji.edu.cn/3d/ee/c10928a146926/page.htm) | 仅入口快照 | 同济官方平台介绍确认WUPEN官网及城市可持续调研竞赛关系；2026智慧低碳交通具体通知深链尚待提取，不能沿用2020规则。官网本次直取超时。 |
| 2026053 | WUPENICITY城市设计学生作业国际竞赛 | A | [赛事站](http://wupen.org/) · [依据](https://caup.tongji.edu.cn/3d/ee/c10928a146926/page.htm) | 仅入口快照 | 同济官方介绍确认WUPEN官网及城市设计学生作业竞赛关系；2026具体通知深链尚待提取，必须与可持续调研分开，不能沿用2020规则。官网本次直取超时。 |
| 2026054 | 全国大学生花园设计建造竞赛 | A | [校内官方通知](https://landscape-caup.tongji.edu.cn/c8/f4/c10586a379124/page.htm) | 读取失败：robots_unavailable | 同济风景园林官方2026社区花园赛道通知；目录总赛有多个赛道。 |
| 2026055 | 全国数字建筑创新应用大赛 | A | [主办／承办方](https://www.ccen.com.cn/info/1150/5937.htm) | 部分读取成功：empty_or_javascript | 中国建设教育协会2026官方通知，报名站bisai.ccen.com.cn；全国报名7月31日结束，优先监测主办方公开通知。 |
| 2026056 | 亚洲建筑师协会学生设计竞赛 | A | [赛事站](https://arcasia.org/awards/arcasia-students-architectural-design-competition-2026/) · [依据](https://arcasia.org/arcasia-student-design-competition/) | 部分读取成功：empty_or_javascript | ARCASIA官方学生设计赛专页；2026届已有明确规则，非专业建筑师奖。 |
| 2026057 | 第十届全国大学生物流设计大赛 | A | [赛事站](https://wlsjds.clpp.org.cn/) · [依据](https://wlsjds.clpp.org.cn/about) | 暂停 | 保留已确认的组委会登录平台。补查发现平台公开about链接旧公开官网http://dspt.clppx.org.cn/pkIndex/wlsj/wlsjdshome，但实际读取超时；中国物流学会公开工作报告https://csl.chinawuliu.com.cn/html/19890796.html检索可见第九届2025赛事，实际读取超时。尚未核实第十届正式通知或可靠可读新闻入口，不把第九届期限当第十届。 |
| 2026058 | 第十届全国高校智能交通创新与创业大赛 | A | [赛事站](https://www.itsnet.cn/) | 读取成功 | 赛事官网显示第十届通知；目录写2026，应再核验通知实际年度与阶段。 |
| 2026059 | 全国大学生电子商务“创新、创意及创业”挑战赛 | A | [赛事站](https://www.3chuang.net/) | 读取失败：empty_or_javascript | 三创赛官方通知站，2026第十六届；常规赛与实战赛分别核对。 |
| 2026060 | 全国大学生市场调查与分析大赛 | A | [赛事站](https://www.china-cssc.org/list-60-1.html) · [依据](https://xhem.cumt.edu.cn/a0/43/c18406a696387/page.htm) | 读取失败：robots_unavailable | 中国商业统计学会官网专题由2026校方通知明确；2026-09启动第十七届，勿混第十六届。 |
| 2026061 | 全国大学生机器人大赛-Robocon | A | [赛事站](https://www.robocon.org.cn/) · [依据](https://www.robocon.org.cn/h-col-104.html) | 读取成功 | 公开赛事官网，有2026第二十五届通知与结果；与RoboMaster分开。 |
| 2026062 | 日本大学生电动方程式汽车大赛（2026） | A | [赛事站](https://en.jsae.or.jp/formula/fsaej/official_announce/) · [依据](https://en.jsae.or.jp/formula/fsaej/rule/) | 读取成功 | 日本自动车技术会2026 Formula SAE Japan官方页；本项只对应EV class，保留与ICV的类别区分。 |
| 2026063 | 日本大学生方程式汽车大赛（2026） | A | [赛事站](https://en.jsae.or.jp/formula/fsaej/official_announce/) · [依据](https://en.jsae.or.jp/formula/news/) | 读取成功 | 同主站包含EV/ICV官方通知；目录另列电动项，本项具体类别应核对，不能混用两类期限和结果。 |
| 2026064 | IF设计奖（IF Design Award） | A | [赛事站](https://ifdesign.com/en/if-design-award-and-jury) · [依据](https://ifdesign.com/en) | 读取失败：robots_unavailable | iF官方主站，当前已进入2027征集并展示2026获奖；与iF学生奖另行区分。 |
| 2026065 | 红点设计大奖（Red Dot Design Award） | A | [赛事站](https://www.red-dot.org/award) · [依据](https://www.red-dot.org/) | 读取失败：empty_or_javascript | 红点官方；产品设计2027已开放，2026结果仍展示，按奖项类别/年份分开。 |
| 2026066 | 两岸新锐设计竞赛华灿奖 | A | [主办／承办方](https://www.cahe.edu.cn/site/term/906.html) · [依据](https://sam.xatu.edu.cn/info/14948/198385.htm) | 读取失败：robots_unavailable | 2026校方通知明确高教学会专题入口；华灿报名专题预定2026-10-19开放，目前不保证可报名。 |
| 2026067 | 全国工业设计大赛 | A | [待确认线索](https://www.cuidc.net/default.aspx) | 待确认 | 补查同济旧目录出现“全国大学生工业设计大赛”，但本项仅称“全国工业设计大赛”；未找到本项与cuidc的明确一一对应依据，保留待确认，不把近似名称自动合并。 |
| 2026068 | 未来设计师·全国高校数字艺术设计大赛 | A | [赛事站](https://www.ncda.org.cn/) · [依据](https://www.ncda.org.cn/dsjs/dsnr/mtsd/9B6/) | 读取成功 | 已有官方HTML适配及2026真实规则；专题赛与主赛分别建档，报名与投稿区分。 |
| 2026069 | 中美青年创客大赛 | A | [主办／承办方](https://chinaus-maker.cscse.edu.cn/) · [依据](https://www.cscse.edu.cn/cscse/gjhz/zmckds/index.html) | 读取失败：robots_unavailable | 教育部留学服务中心公开赛事官网，有2026章程，参赛操作需登录。 |
| 2026070 | 国际遗传工程机器大赛（IGEM） | A | [赛事站](https://competition.igem.org/) · [依据](https://igem.org/) | 读取失败：empty_or_javascript | 合成生物学iGEM官方，2026团队报名已关闭；不要误选同名马来西亚绿色展会IGEM。 |
| 2026071 | 全国大学生生命科学竞赛（创新创业类） | A | [赛事站](https://culsc.cn/) · [依据](https://www.lncu.edu.cn/cxcyxy/28648.html) | 读取失败：empty_or_javascript | 校方2026创新创业类报名通知佐证官网；与科学探究类分开，同站部分功能为动态页面/登录。 |
| 2026072 | 全国大学生生命科学竞赛（科学探究类） | A | [赛事站](https://culsc.cn/) · [依据](https://culsc.cn/sitehome/) | 读取失败：empty_or_javascript | 公开首页列2026第十一届科学探究通知；/compete/为登录系统，不绕过登录。 |
| 2026073 | 第十八届全国大学生数学竞赛 | A | [赛事站](https://www.cms.org.cn/index.php/Home/comp/comp/cid/16.html) · [依据](https://www.cms.org.cn/Home/comp/comp_details/id/1449.html) | 读取成功 | 中国数学会官方通知，第十八届2026初赛、2027决赛；正文图片需另行解析。 |
| 2026074 | 全国大学生数学建模竞赛(2026) | A | [主办／承办方](https://www.mcm.edu.cn/) · [依据](https://www.mcm.edu.cn/html_cn/node/d6fd7a0ee8f3a3d525e30af1c365fcec.html) | 读取成功 | 官方2026通知已核验，9月比赛已结束；全国上报截止与学校报名需区分，附件可能扫描PDF。 |
| 2026075 | 全国大学生统计建模大赛（2026） | A | [赛事站](https://www.ai-learning.net/) · [依据](https://www.ai-learning.net/dstz/37119.jhtml) | 读取失败：robots_unavailable | 中国统计教育学会赛事官方站2026第十二届；已公布结果，区分市场调查大赛。 |
| 2026076 | 美国ASCE大学生土木工程竞赛 | A | [赛事站](https://www.asce.org/communities/student-members/conferences) · [依据](https://www.asce.org/communities/student-members/conferences/asce-civil-engineering-student-championships) | 读取成功 | ASCE官方学生竞赛总入口；多项目/地区分会，大赛页已转2027，2026须查对应历史通知。 |
| 2026077 | 全国大学生结构设计竞赛 | A | [赛事站](http://www.structurecontest.com/home) · [依据](https://www.lit.edu.cn/info/1042/66156.htm) | 读取失败：empty_or_javascript | 2026校方通知明确全国官网；各省子域为分区赛，不代表同济校内截止；实际可用性需运行时确认。 本次全国官网直取502。 |
| 2026078 | 全国高校BIM毕业设计创新大赛 | A | [赛事站](https://gxbsxs.glodonedu.com/) · [依据](https://www.zbu.edu.cn/jgxy/2025/1113/c651a106904/pagem.htm) | 读取失败：empty_or_javascript | 校方第十二届通知明确官方入口；官网目前已换第十三届，2025启动/2026决赛的第十二届与新届须分开，目录全国称谓对应现国际高校名称需保留原名。公开正文依赖JavaScript。 |
| 2026079 | “外研社·国才杯”“理解当代中国”全国大学生外语能力大赛（德语组） | A | [赛事站](https://ucc.fltrp.com/news/) · [依据](https://ucc.fltrp.com/dslc/) | 读取成功 | 外研社官方2026大赛；德语属于多语种组，须与英语及日语记录分别匹配赛项通知。 |
| 2026080 | “外研社·国才杯”“理解当代中国”全国大学生外语能力大赛（日语组） | A | [赛事站](https://ucc.fltrp.com/news/) · [依据](https://ucc.fltrp.com/dslc/) | 读取成功 | 外研社官方2026大赛；日语属于多语种组，须与英语及德语记录分别匹配赛项通知。 |
| 2026081 | “外研社·国才杯”“理解当代中国”全国大学生外语能力大赛（英语组） | A | [赛事站](https://ucc.fltrp.com/news/) · [依据](https://ucc.fltrp.com/dslc/) | 读取成功 | 外研社官方2026大赛；英语组包括不同赛项，报名与省赛截止须按具体通知区分。 |
| 2026082 | 第31届“21世纪杯”全国英语演讲比赛 | A | [赛事站](https://contest.i21st.cn/college/) · [依据](https://contest.i21st.cn/) | 读取成功 | 中国日报社第31届大学生英语演讲比赛官方入口，须区分少儿及其他组别。 |
| 2026083 | 第九届“外教社杯”全国高校学生跨文化能力大赛 | A | [赛事站](https://ict.sflep.com/index.php) · [依据](https://due.xjtu.edu.cn/info/1172/9923.htm) | 读取成功 | 上海外语教育出版社跨文化能力大赛官方中心，已见2026第九届通知，短视频与常规赛项应区分。 |
| 2026084 | 全国大学生英语竞赛 | A | [赛事站](https://www.chinaneccs.cn/) · [依据](https://www.htu.edu.cn/fl/2025/1222/c3410a367249/page.htm) | 读取失败：empty_or_javascript | 2026主办方通知由校方确认官网；直取仅要求启用JavaScript，公开正文采集需适配，不能绕过登录。A/B/C/D组不得混用。 |
| 2026085 | 全国大学生光电设计竞赛 | A | [赛事站](https://gd.moocollege.com/home) · [依据](https://opt.cas.cn/rsjyc/yjsjy/yjstz/202006/P020250822616364966695.pdf) | 读取失败：empty_or_javascript | 第十四届2026光电设计全国赛入口；主赛道、光学设计赛道及分区分别报名，公开站正文依赖JavaScript。 |
| 2026086 | 全国大学生物理实验竞赛（创新）（2026） | A | [赛事站](https://wlsycx.moocollege.com/) · [依据](https://physics.hit.edu.cn/2026/0310/c12332a388020/page.htm) | 读取失败：empty_or_javascript | 官方赛事站公开赛事动态；2026正式报名9月24日截止，当前已过期。 |
| 2026087 | 第三届全国大学生职业规划大赛 | A | [主办／承办方](https://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/s5987/202510/t20251021_1417590.html) · [依据](https://www.moe.gov.cn/srcsite/A15/s7063/202609/t20260902_1448809.html) | 读取成功 | 教育部与天津市人民政府主办；第三届已于2026年4月完成总决赛，使用教育部公开通知监测，报名系统另行核验。 |
| 2026088 | 全国大学生医学创新大赛暨“一带一路”国际竞赛 | A | [赛事站](https://www.jcyxds.com/) · [依据](https://www.qmu.edu.cn/2026/0313/c345a202083/page.htm) | 读取失败：robots_unavailable | 医学创新赛事官方站有公开通知；高等学校大学生医学创新竞赛委员会组织，2026报名阶段已过。 |
| 2026089 | 大学生数字媒体科技作品及创意竞赛 | A | [赛事站](https://www.cmit.cn/) · [依据](https://www.cmit.cn/index.php) | 部分读取成功：robots_disallowed | 数媒竞赛官方站有2026第十四届通知与赛程；公开HTML列表可作为监测入口。 |
| 2026090 | 第八届中华经典诵写讲大赛“诵读中国”经典诵读大赛 | A | [主办／承办方](https://www.moe.gov.cn/srcsite/A18/s3137/202605/t20260528_1437956.html) | 仅入口快照 | 教育部、国家语委2026正式通知及诵读中国方案，官网具体活动入口待追加核验。 |
| 2026091 | 米兰设计周-中国高校设计学科师生优秀作品展及专项赛 | A | [赛事站](https://www.milan-aap.org.cn/) · [依据](https://xg.cj.upc.edu.cn/2026/0324/c13761a279318/page.htm) | 读取失败：empty_or_javascript | 赛事组委会站有2026作品展和专项赛通知；专项赛须按各自期限，不沿用年度展截止。 |
| 2026092 | 全国大学生广告艺术大赛 | A | [赛事站](https://www.sun-ada.net/) · [依据](https://www.ahpu.edu.cn/ysxy/2026/0414/c2185a267493/page.htm) | 读取成功 | 大广赛官网及高校2026通知互证，有公开参赛通知/命题/赛区入口。 |
| 2026093 | 中国好创意暨全国数字艺术设计大赛 | A | [赛事站](https://www.cdec.org.cn/) · [依据](https://jwc.cugb.edu.cn/c/2026-03-18/845660.shtml) | 读取成功 | 好创意组委会公开官网，高校通知明确该报名域名；投稿系统需登录，不采集登录内容。 |
| 2026094 | 全国大学生微结构摄影大赛（上海赛区） | B | [主办／承办方](https://weijiegou.sjtu.edu.cn/) · [依据](https://ccbm.ecut.edu.cn/8d/fa/c7122a101882/page.htm) | 读取失败：robots_unavailable | 高校正式通知明确赛事官网，主办含中国材料研究学会、上海显微学学会和上海交大；当前2026上海赛区独立通知未确认。 |
| 2026095 | 上海市先进材料创新创意大赛 | B | [主办／承办方](https://chxy.usst.edu.cn/2012/0815/c3681a66841/page.htm) | 仅入口快照 | 实际打开上海理工2012第一届章程，名称确为上海市大学生先进材料创新创意大赛、上海教委主办。解决旧系列来源，2026新材料赛更名关系仍待证，不把其当年日期套用。 |
| 2026096 | VEX机器人亚洲公开赛 | B | [赛事站](https://istemn.cn/) · [依据](https://istemn.cn/portal/article/index.html?id=122) | 读取成功 | 爱因斯坦联盟为该赛事组委会，公开赛季通知；须筛选VEX U大学组，不能用青少年城市赛直接替代。 |
| 2026097 | 高校电气电子工程创新大赛 | B | [赛事站](https://eeeic.ces.org.cn/) · [依据](https://www.ces.org.cn/html/report/26062783-1.htm) | 读取成功 | 中国电工技术学会赛事平台，2026报名4月1日截止，公开通知持续更新。 |
| 2026098 | 国际青年人工智能大赛 | B | [赛事站](https://www.iyaic.com/col.jsp?id=127) · [依据](https://www.iyaic.com/col.jsp?id=125) | 读取成功 | 赛事组委会公开通知栏，已有2026第八届通知；大学组与青少年组须分开。 |
| 2026099 | 国际先进机器人及仿真技术大赛 | B | [赛事站](https://www.ilur.org/) · [依据](https://jcsysx.shmtu.edu.cn/2026/0414/c12467a289949/page.htm) | 暂停 | 高校2026通知明确第十九届官网www.ilur.org；该域名本次工具不可访问，不能保证公开HTML支持，非主办高校通知仅作身份核对依据。 |
| 2026100 | 全国大学生电子设计竞赛嵌入式系统专题赛 | B | [主办／承办方](https://nuedc.xjtu.edu.cn/) · [依据](https://nuedc.sjtu.edu.cn/ckfinder/userfiles/files/%E5%85%B3%E4%BA%8E%E7%BB%84%E7%BB%872026%E5%B9%B4%E5%85%A8%E5%9B%BD%E5%A4%A7%E5%AD%A6%E7%94%9F%E7%94%B5%E5%AD%90%E8%AE%BE%E8%AE%A1%E7%AB%9E%E8%B5%9B%E4%B8%93%E9%A2%98%E7%AB%9E%E8%B5%9B%E7%9A%84%E9%80%9A%E7%9F%A5.pdf) | 读取失败：robots_unavailable | 全国电赛组委会站；2026名称为嵌入式AI专题赛（英特尔杯），按专项通知区分总赛。 |
| 2026101 | 全国大学生电子设计竞赛信息技术前沿专题赛 | B | [主办／承办方](https://nuedc.xjtu.edu.cn/) · [依据](https://www.nuedc-training.com.cn/index/news/details/new_id/342) | 读取失败：robots_unavailable | 组委会2026信息科技前沿专题赛通知明确aitic.xjtu.edu.cn专项入口，主站可读通知用于监测。 |
| 2026102 | 全球人工智能技术创新大赛 | B | [赛事站](https://gaiic.caai.cn/robot2023/) · [依据](https://gaiic.tianchi.aliyun.com/) | 读取失败：robots_unavailable | 中国人工智能学会赛事站及阿里天池历史专站；目前核查到历史届次，不能标成2026开放报名，动态天池子赛页面需另适配。 |
| 2026103 | 智能无人系统应用挑战赛 | B | [赛事站](https://icaus2026.scimeeting.cn/cn/web/index/34629_3046283) | 仅入口快照 | 2026国际自主无人系统大会官方挑战赛页，公开主办名单与赛程，2026赛期8月已过。 |
| 2026104 | 中国智能机器人格斗及竞技大赛 | B | [主办／承办方](https://me.bit.edu.cn/xyxw/a3fa540574614265ba1afc8cd34d502e.htm) | 仅入口快照 | 实际打开共同承办北京理工机械学院2025决赛报道，明确同名赛事及承办身份；2026征集未核，采用历史官方通知监测入口。 |
| 2026105 | FDI模拟投资仲裁竞赛（FDI Moot） | B | [赛事站](https://fdimoot.org/) · [依据](https://fdimoot.org/regionals.php) | 读取成功 | FDI Moot主办官方站，2026总决赛深圳；公开区域赛、规则和日程，深圳选拔fdiscia.lexmoot.com与全球赛分别记录。 |
| 2026106 | 国际公法模拟法庭竞赛（Phillip C. Jessup） | B | [主办／承办方](https://www.ilsa.org/) · [依据](https://www.ilsa.org/jessup/) | 仅入口快照 | ILSA主办官网，公开Jessup新闻、规则与赛历；当前网站已进入2027届，不把赛事报名年份与目录年混同。 |
| 2026107 | 国际商事模拟仲裁庭辩论赛（Vis Moot） | B | [赛事站](https://www.vismoot.org/) · [依据](https://www.vismoot.org/home/34th-vis-moot/) | 读取成功 | Vis Moot官方站，34届2026报名/2027比赛，公开规则及日程。 |
| 2026108 | 国际刑事法院模拟法庭竞赛（ICC） | B | [赛事站](https://www.iccmoot.com/) · [依据](https://iccmoot.com/wp-content/uploads/2025/08/ROPs-IBA-ICCMCC-2026.pdf) | 读取成功 | 莱顿大学Grotius Centre与IBA组织的ICC英文赛官网；中文版须另找中国区通知，不能直接混合。 |
| 2026109 | 红十字国际人道法模拟法庭比赛 | B | [赛事站](https://www.icrc.org/zh/article/china-19th-national-moot-court-problem-2025) · [依据](https://www.icrc.org/zh/article/china-19th-ihl-moot-court-concludes-wuhan-2025) | 读取失败：empty_or_javascript | ICRC中国大陆赛官方报名通知，2025大陆赛晋级2026亚太赛；新届大陆通知待发布核验。 |
| 2026110 | 全国法律英语大赛 | B | [校内官方通知](https://law.tongji.edu.cn/sjjx.htm) · [依据](https://law.tongji.edu.cn/info/1355/8537.htm) | 读取失败：robots_unavailable | 实际打开同济法学院2026-03-27第二号正式通知；正文同济为华东赛区承办，2026-04-10 24:00报名截止、05-30决赛，已结束。列表可持续监测，不与新创LEC实务赛混同。 |
| 2026111 | 上海市大学生模拟法庭 | B | [待确认线索](https://law.tongji.edu.cn/info/1088/4918.htm) | 待确认 | 补查找到同济法学院参与“金法槌”上海市模拟法庭竞赛历史报道；尚不能证明本目录简称唯一对应该赛或其它模拟法庭活动，未找到本项2026主办正式通知，保留待确认。 |
| 2026112 | 全国大学生地球物理知识竞赛（2026） | B | [主办／承办方](https://www.cgs.org.cn/) | 读取成功 | 中国地球物理学会主办官网公开2026第十一届创新杯报道；赛期5月已过，监测同名赛事新通知。 |
| 2026113 | 全国大学生地质技能竞赛（2026） | B | [主办／承办方](https://geosociety.org.cn/?v1=v40&v4=v21&v6=2) · [依据](https://www.geosociety.org.cn/?v1=v14&v2=6a4b786b3ad3f&v3=v41&v4=v21) | 读取成功 | 中国地质学会2026第八届一、二号通知可发现；正文多为扫描图片，需人工核验/OCR，不能空正文自动填日期。 |
| 2026114 | 全国大学生海洋知识竞赛（2026） | B | [待确认线索](https://youth.tongji.edu.cn/info/1004/1588.htm) | 待确认 | 补查仅找到同济2013第六届全国大中学生海洋知识竞赛历史通知，另有学院校内海洋知识活动；与目录2026全国大学生项的名称/届次未建立明确对应关系，不使用同名在线答题聚合站替代官方。 |
| 2026115 | 2026“上纬杯”第十一届全国大学生复合材料设计与制作大赛 | B | [赛事站](https://shenzhen.chinacompositesexpo.com/cn/news.php?_MULTI_PAGE_START=0&c_id=128) · [依据](https://jxxy.fzu.edu.cn/info/1023/12343.htm) | 读取成功 | 组委会公开2026第十一届‘CCE’杯通知；高校确认原‘上纬杯’，9月比赛已结束。 |
| 2026116 | 2026国际空间科学与载荷大赛 | B | [主办／承办方](https://isssp.bit.edu.cn/) · [依据](https://aao.nuaa.edu.cn/2026/0206/c11066a393145/page.htm) | 暂停 | 南航2026通知明确isssp.bit.edu.cn报名官网、亚太空间合作组织与北理工联合举办；本次官网超时。需实际重试，不把南航转载作为主办监测入口。 |
| 2026117 | 2026年教育部本科毕业设计成果展（航空专业） | B | [主办／承办方](https://aerospace.xmu.edu.cn/info/2043/63664.htm) · [依据](https://ae.cqu.edu.cn/info/1312/9005.htm) | 读取成功 | 2026实际名称为全国高校航空航天类专业本科毕业设计成果交流会，教指委主办、厦大承办；已结束，目录简称映射宜人工确认。 |
| 2026118 | 2026年上海市未来飞行器设计大赛 | B | [待确认线索](https://aero-mech.tongji.edu.cn/11/4c/c22241a201036/page.htm) | 待确认 | 补查同济航空学院介绍及2018第八届通知均为“同济大学未来飞行器设计大赛”，尚未证实目录“上海市未来飞行器设计大赛”与其同一赛事，亦不自动等同全国创新杯上海赛区。 |
| 2026119 | 2026中国大学生飞行器设计创新大赛 | B | [赛事站](https://www.cuadc.cn/News.aspx?ClassID=7) · [依据](https://www.cuadc.cn/) | 读取失败：empty_or_javascript | 中国航空学会主办CUADC官方通知列表，2026分区赛与总决赛需分别读取。 |
| 2026120 | 第七届国际大学生工程力学竞赛（亚洲赛区） | B | [主办／承办方](https://lxzx.hhu.edu.cn/2026/0805/c15373a332887/page.htm) · [依据](https://eng.nbu.edu.cn/info/1432/45513.htm) | 仅入口快照 | 亚洲赛区承办河海大学官方报道第六届开幕；页面2026-08-05但正文为12月6日已办赛事，存在迁站日期错位，不能推断2026第七届报名。 |
| 2026121 | 第七届力学超材料大赛 | B | [主办／承办方](https://aero.nuaa.edu.cn/_t385/2026/0724/c4293a406173/page.htm) | 读取失败：empty_or_javascript | 南航官方第七届超材料力学大赛第一轮通知，附件为报名与作品模板；目录名词顺序不同，正文/附件需继续核读。 |
| 2026122 | 第七届上海市大学生力学竞赛个人赛 | B | [赛事站](https://www.sstam.org.cn/) · [依据](https://siamm.shu.edu.cn/) | 暂停 | 已实读上海大学应用数学和力学研究所官网，友情链接明确指向上海市力学学会www.sstam.org.cn，确认主办学会官网；学会站此次访问超时，未实读第七届正式章程，不从参与学校报名时间推断全市截止；待采集器复测。 |
| 2026123 | 第七届上海市大学生力学竞赛团体赛 | B | [赛事站](https://www.sstam.org.cn/) · [依据](https://siamm.shu.edu.cn/) | 暂停 | 已实读上海大学应用数学和力学研究所官网，友情链接明确指向上海市力学学会www.sstam.org.cn，确认主办学会官网；学会站此次访问超时，未实读第七届正式章程，不从参与学校报名时间推断全市截止；待采集器复测。 |
| 2026124 | 第十届“光威杯”中国复合材料学会大学生科技创新竞赛 | B | [主办／承办方](https://www.csfcm.org.cn/) · [依据](https://www.csfcm.org.cn/site/content/4191.html) | 读取成功 | 中国复合材料学会主办，2026第十届报名通知/延期与半决赛公告可公开抓取。 |
| 2026125 | 第五届国际奥林匹克互联网学科竞赛“材料力学” | B | [赛事站](https://tdbgi.edu.tm/en/notice) · [依据](https://tdbgi.edu.tm/en/news/658?source=local) | 读取成功 | 实际打开主办土库曼斯坦国立建筑学院公告列表及2026第五届成绩原文；2026-03-18已举行，名单不采集个人信息。列表可监测后续赛季。 |
| 2026126 | 第五届国际奥林匹克互联网学科竞赛“理论力学” | B | [赛事站](https://turkmenistan.gov.tm/en/post/102661/energy-institute-turkmenistan-invites-students-5th-international-olympiad-theoretical-mechanics) | 仅入口快照 | 实际打开土库曼斯坦国家通讯社2026正式报名公告：第五届理论力学赛主办国立能源学院，3月15报名截止、3月24至28竞赛，已结束；原文链接主办官网www.tdei.edu.tm。 |
| 2026127 | 中国大学生机械工程创新创意大赛-“欧波同杯”失效分析赛 | B | [赛事站](https://www.shixiaofenxisai.com/FileDownload.aspx?bigid=33) · [依据](https://www.shixiaofenxisai.com/) | 读取成功 | 欧波同杯官网通知列表，中国机械工程学会主办；2026第十一届7月比赛已过。 |
| 2026128 | “SCIP+”绿色化学化工创新创业大赛 | B | [主办／承办方](https://www.scip.com.cn/kechuang/act.html) · [依据](https://www.shanghai.gov.cn/nw31406/20260616/642d7f1f90e44287acadcdebc2f273c5.html) | 仅入口快照 | 上海化工区官方赛事栏与上海市政府互证，2026实际报名页https://makeable.cn/2026-scip-cn/；与目录135重复赛事勿重复建卡。 |
| 2026129 | 全国大学生电化学测量技术竞赛 | B | [赛事站](https://ecmt.cteic.com/index/Index/notice?news_type=2) · [依据](https://ecmt.cteic.com/) | 读取失败：robots_unavailable | 中国化工教育协会ECMT官方竞赛文件列表，2026第五届已结束；不将证书申领期限当报名截止。 |
| 2026130 | 全国大学生化学实验竞赛 | B | [主办／承办方](https://news.bnu.edu.cn/zx/zhxw/2f1fd28c730840c09c65aaff0d8bc0cb.htm) | 仅入口快照 | 实际打开2026承办北师大8月18官方报道，2026决赛8月10至13已举行；正文明确2024从全国大学生化学实验邀请赛更名。北大化学教育研究所/rice为主办研究中心平台，并非一般学校转载，当前网页读取超时。 |
| 2026131 | 全国化学类专业大学生科技活动交流 | B | [主办／承办方](https://chem.xmu.edu.cn/info/1273/121205.htm) | 读取成功 | 化学教指委主办，高校官方确认2026第十届由厦大承办；当前核实到承办信息，未核到2026征集细则。 |
| 2026132 | 上海市大学生化学化工优秀毕业论文（设计）大赛 | B | [主办／承办方](https://www.sscci.org/personnel/shownews.php?id=791) · [依据](https://www.sues.edu.cn/8a/b7/c27396a297655/page.htm) | 读取成功 | 上海市化学化工学会主办官网，2026第29届6月9日已举行。 |
| 2026133 | 第十一届“汇创青春”——大学生文化创意作品展示活动（环境设计类） | B | [主办／承办方](https://edu.sh.gov.cn/xxgk2_zdgz_gdjy_12/20260403/fc367a2adaea4e1797f412fa0444a0b1.html) · [依据](https://ien.shou.edu.cn/2026/0313/c15062a350984/page.htm) | 读取失败：empty_or_javascript | 上海市教委2026第十一届正式通知含环境设计；分项要求在附件，校内截止不得跨校照搬。 |
| 2026134 | DWA全球高校挑战赛中国选拔赛 | B | [校内官方通知](https://sese.tongji.edu.cn/info/1236/9608.htm) · [依据](https://en.dwa.de/en/university-challenge.html) | 读取失败：robots_unavailable | 同济环境学院为中国选拔主办方，2026年4月15日已举办；DWA全球赛官方页可作为后续赛季补充，国内选拔须独立识别。 |
| 2026135 | SCIP+绿色化学化工创新创业大赛 | B | [主办／承办方](https://www.scip.com.cn/kechuang/act.html) · [依据](https://www.shanghai.gov.cn/nw31406/20260616/642d7f1f90e44287acadcdebc2f273c5.html) | 仅入口快照 | 与目录2026128同名赛事仅标点不同，共用来源与年度赛事，避免重复。 |
| 2026136 | 全国大学生市政环境类创新实践能力大赛 | B | [校内官方通知](https://sese.tongji.edu.cn/info/1236/9307.htm) | 读取失败：robots_unavailable | 实际打开同济环境学院共同主办2025第七届市政环境AI+赛报道；确认主办及系列正式渠道，2026第八届另有基金会实施证据但未核报名细则，勿把旧届日期延用。 |
| 2026137 | 全国环境友好科技竞赛 | B | [主办／承办方](https://www.env.tsinghua.edu.cn/info/1237/6064.htm) · [依据](https://jwc.yznu.edu.cn/2026/0515/c1802a278968/page.htm) | 部分读取成功：empty_or_javascript | 清华环境学院确认hjyh.env.tsinghua.edu.cn官方站；2026理念/实物类使用赛氪官方授权报名，聚合平台不作为独立官方来源。 |
| 2026138 | 世界技能大赛上海选拔赛（水处理技术） | B | [主办／承办方](https://rsj.sh.gov.cn/t2023zxsk_17783/20230506/49f9d35612fe48b1afe7db2ef0b263d7.html) · [依据](https://news.tongji.edu.cn/info/1003/75174.htm) | 仅入口快照 | 上海人社及同济官方确认水处理技术上海选拔体系；当前仅核到往届，不能用2026世赛观众预约或水务行业赛代替报名。 |
| 2026139 | 长三角大学生可持续水处理竞赛 | B | 待确认 | 待确认 | 围绕准确名称及“长三角”“可持续水处理”组合补查，未找到主办方正式公开通知或可证实的独立官网，保持待确认。 |
| 2026140 | 第十一届“汇创青春”——大学生文化创意作品展示活动（互联网+文创类） | B | [主办／承办方](https://edu.sh.gov.cn/xxgk2_zdgz_gdjy_12/20260403/fc367a2adaea4e1797f412fa0444a0b1.html) · [依据](https://gcxy.shou.edu.cn/2026/0325/c11246a351362/page.htm) | 读取失败：empty_or_javascript | 上海市教委总通知含互联网+数字文创，互联网+文创具体附件由高校公开发布，与环境设计分项分开。 |
| 2026141 | Apple WWDC Students Scholarship | B | [主办／承办方](https://developer.apple.com/swift-student-challenge/) · [依据](https://developer.apple.com/swift-student-challenge/eligibility/) | 读取成功 | Apple官方当前学生竞赛为Swift Student Challenge；目录旧称WWDC Student Scholarship须保留别名，不能当两项；提交需开发者登录。 |
| 2026142 | CCF大数据与计算智能大赛（BDCI） | B | [赛事站](https://tc.ccf.org.cn/tfbd/xwdt/tzgg/) · [依据](https://tc.ccf.org.cn/tfbd/xwdt/tzgg/2022-08-11/767448.shtml) | 仅入口快照 | CCF大数据专委会正式通知可验证主办与历史DataFountain官网；2026出现xir.cn赛事页，但新版授权映射未完成，暂监测主办通知。 |
| 2026143 | CCF大学生计算机系统与程序设计竞赛（CCSP） | B | [赛事站](https://ccsp.ccf.org.cn/) · [依据](https://ccsp.ccf.org.cn/ccsp/jszc/) | 读取成功 | 中国计算机学会CCSP官网，2026通知已公开；CSP为初赛，不将两者报名截止混用。 |
| 2026144 | CCPC全国大学生程序设计竞赛 | B | [赛事站](https://ccpc.io/) · [依据](https://www.board.ccpc.io/placard) | 读取失败：empty_or_javascript | 中国大学生程序设计竞赛组委会官网及公告；报名系统仅作跳转，不采集账户数据。 |
| 2026145 | 蓝桥杯全国软件和信息技术专业人才大赛 | B | [赛事站](https://dasai.lanqiao.cn/) · [依据](https://jwc.ustb.edu.cn/tztg/2512ca996a6248249300d358b4e2f325.htm) | 暂停 | 高校2026正式通知证实蓝桥杯官网；本次返回HTML无可读正文（0行），需JS接口/页面专用适配，不用高校校内截止代替正赛截止。 |
| 2026146 | 码蹄杯全国大学生程序设计大赛 | B | [赛事站](https://www.matiji.net/exam/contest/topic2026?id=68) · [依据](https://jsj.suse.edu.cn/2026/0108/c3314a205573/page.htm) | 暂停 | 高校2026通知明确matiji.net/matibei；实读跳转官方2026专题页面但无可读正文（0行），需要动态页面适配。 |
| 2026147 | 强网杯全国网络安全挑战赛 | B | [主办／承办方](https://www.cac.gov.cn/2025-09/09/c_1759136409566616.htm) · [依据](https://www.cac.gov.cn/2020-08/03/c_1598010258044729.htm) | 仅入口快照 | 中央网信办公开赛事通知；历史官网qiangwangbei.com已被官方引用，但当前第九届详情主走公众号，不承诺静态官网可采。 |
| 2026148 | 全国大学生软件创新大赛 | B | [主办／承办方](https://www.pses.com.cn/) | 读取成功 | 示范性软件学院联盟主办官网公开第十九届2026赛事资讯，正式报名站swcontest.com.cn需按主办通知链接逐届核验。 |
| 2026149 | 上海市大学生程序设计竞赛 | B | [主办／承办方](https://www.shu.edu.cn/info/1056/378595.htm) | 仅入口快照 | 上海大学公开2025上海市赛承办报道；EOJ月赛与年度上海市赛须区分，尚未核实2026年度正式通知。 |
| 2026150 | 上海市大学生计算机应用能力大赛 | B | [校内官方通知](https://cs.tongji.edu.cn/info/1054/3911.htm) | 读取失败：robots_unavailable | 已实读同济计算机学院2026-01-13校内选拔通知及主赛说明：上海市教委主办，第十八届；校内选拔报名2026-02-26 24:00、作品提交4-16 24:00均已过。监测同济校内组织通知，不当作主赛全国官网；不得把计算机设计国赛链接替代本赛事。 |
| 2026151 | 上海市大学生网络安全大赛 | B | [主办／承办方](https://shwas.dhu.edu.cn/) · [依据](https://shwas.dhu.edu.cn/_upload/article/files/63/42/4d00d1eb477caffdc829f9c7b5f5/4e40b5cf-ab8f-47e1-b442-f5e4203fb32a.pdf) | 读取成功 | 东华大学托管组委会官网可证；当前公开站内容为历史2016届，2026新通知目前仅见转载，不能标成2026当前报名。 |
| 2026152 | 网鼎杯网络安全大赛 | B | [赛事站](https://www.wangdingcup.com/) · [依据](https://www.wangdingcup.com/assets/notice/%E7%AC%AC%E5%9B%9B%E5%B1%8A%E2%80%9C%E7%BD%91%E9%BC%8E%E6%9D%AF%E2%80%9D%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8%E5%A4%A7%E8%B5%9B%E8%A7%84%E5%88%99.pdf) | 读取失败：empty_or_javascript | 组委会官网和规则可公开读取，当前核到第四届2024规则，不推测新届时间；高校属于青龙组。 |
| 2026153 | “天作奖”国际大学生建筑设计竞赛 | B | [主办／承办方](https://jzss.cbpt.cnki.net/portal/journal/portal/client/index) · [依据](https://jzss.cbpt.cnki.net/portal/journal/portal/client/paper/94c2bc530e561600fa5a78899b3ba6fa) | 仅入口快照 | 《建筑师》杂志官方期刊平台证实主办及2026天作奖通知，正文/下载可能受期刊平台限制。 |
| 2026154 | ASLA 学生竞赛 | B | [主办／承办方](https://www.asla.org/awards-events-main-landing/honors-awards/pro-student-awards/2026-student-cfe) · [依据](https://www.asla.org/awards-events-main-landing/honors-awards/pro-student-awards/2026-asla-student-awards) | 仅入口快照 | ASLA官方2026学生奖征集及结果页；2026结果已公布，不作仍报名。须满足ASLA学生会员等资格。 |
| 2026155 | IFLA 国际学生竞赛 | B | [赛事站](https://www.iflaworld.com/student-competition) · [依据](https://www.iflaworld.com/eaa-student-awards-working-group) | 仅入口快照 | 国际风景园林师联合会官网；官方说明2026起改为世界大会汇聚区域优秀学生项目的机制，不能套用往届独立征稿时间。切勿误用图书馆联合会ifla.org。 |
| 2026156 | ULI Hines Student Competition | B | [赛事站](https://asia.uli.org/programs/awards-and-competition/uli-hines-student-competition-asia-pacific/) · [依据](https://asia.uli.org/wp-content/uploads/2025/11/2026-Hines-2-page-Flyer_EN.pdf) | 读取失败：robots_unavailable | ULI官方亚太赛2026材料确认中国高校可参加、跨至少2学科3至5人；亚太/欧洲/北美资格不同。仅记录官方已公开赛季，不推断当前仍报名。 |
| 2026157 | WUPENICITY城市可持续调研报告国际竞赛 | B | [赛事站](http://wupen.org/) · [依据](https://caup.tongji.edu.cn/3d/ee/c10928a146926/page.htm) | 暂停 | 同济官方介绍确认WUPEN平台域名；本次HTTPS读取502，2026调研赛已有高校获奖报道，不能称仍报名。需复核公开页面/JS访问后启用，不以城市设计赛具体日期代替调研报告赛。 |
| 2026158 | 第六届全国城乡建成遗产保护设计优秀作业评选 | B | [主办／承办方](https://jzxy.bucea.edu.cn/xyxx/xwxx/1c04fde13b854d75a397afd8d4718276.htm) · [依据](https://jianzhuyichan.tongji.edu.cn/info/1427/2120.htm) | 读取失败：robots_unavailable | 共同主办及当届承办北京建筑大学公开2026征集；截止2026-09-10，最多3人。正文称第五届而目录为第六届，届次冲突需人工核对，不能自动匹配精确届次。 |
| 2026159 | 国际绿点大赛 | B | [赛事站](https://www.planning.org.cn/) · [依据](https://castjournals.cast.org.cn/joweb/kjdb/CN/2019/37/12) | 读取成功 | 科协主办期刊2019报道证实中国城市规划学会承办首届国际绿点大赛；仅确认主办/承办组织监测域名，未查到2026征集，不与绿色概念奖/绿色设计赛合并。 |
| 2026160 | 中国城市规划学会科技奖优秀科技论文专项奖（求是） | B | [赛事站](https://www.planning.org.cn/) · [依据](https://m.thepaper.cn/newsDetail_forward_6535140) | 读取成功 | 学会官方澎湃号2020征文证实求是为优秀科技论文子奖项；官网可监测组织通知，未核到2026求是征文。不可用2026科技进步奖代替论文奖。 |
| 2026161 | 中国风景园林教育大会毕业设计作品 | B | [赛事站](https://jchla.ijournals.cn/ch/reader/more_news_list.aspx?category_id=yjxx&category_name=%E4%B8%9A%E7%95%8C%E4%BF%A1%E6%81%AF&order_field=send_time&order_type=desc) · [依据](https://yyyl.swu.edu.cn/info/1064/4242.htm) | 仅入口快照 | 2025承办西南大学证实教育大会及优秀毕设活动；主办学会期刊列表已有2026第十五届教育大会公告，但详细跳转公众号，尚未核实本年度本科毕设征集，不能拿研究生论坛期限代替。 |
| 2026162 | 中国风景园林学会大学生设计竞赛 | B | [赛事站](https://jchla.ijournals.cn/ch/reader/more_news_list.aspx?category_id=yjxx&category_name=%E4%B8%9A%E7%95%8C%E4%BF%A1%E6%81%AF&order_field=send_time&order_type=desc) · [依据](https://jchla.ijournals.cn/ch/reader/view_news.aspx?id=20260813104414001) | 部分读取成功：unsafe_url | 中国风景园林学会主办《中国园林》期刊官网列表2026-08-13征集；详情跳转公众号mp.weixin.qq.com/s/GpimtJQSOznga76TaGtQaA，列表可监测但正文采集需单独处理。8月31日有报名倒计时5天提醒，不能当当前报名中。 |
| 2026163 | 中国人居环境设计学年奖 | B | [主办／承办方](https://www.ad.tsinghua.edu.cn/info/1061/7632.htm) | 部分读取成功：empty_or_javascript | 主办清华大学美院官方2020报道确认赛事归属；2026征稿目前仅核到转载指向www.xuenianjiang.com，本次该站超时，先保留主办方历史页面，不给当年度报名结论。 |
| 2026164 | 中国自然资源学会“国地杯”第八届全国大学生自然资源科技作品大赛 | B | [赛事站](https://www.csnr.org.cn/list.html?id=43) · [依据](https://www.csnr.org.cn/detail.html?contentId=1009&id=65) | 读取成功 | 中国自然资源学会官方2026第八届一号通知及大学生竞赛栏目；按学校提交报名材料，不能把2026发布的第七届2025决赛报道当新届报名。 |
| 2026165 | 中日韩风景园林学生竞赛 | B | [赛事站](https://www.chsla.org.cn/) · [依据](https://www.ad.tsinghua.edu.cn/info/1219/25876.htm) | 暂停 | 清华官方2020竞赛获奖报道证实中日韩三国学会联合主办；中国风景园林学会官网本次403，2026具体赛事未核实。仅历史身份依据，需可读主办通知再采集。 |
| 2026166 | OnSite自动驾驶算法挑战赛 | B | [赛事站](https://onsite.com.cn/) · [依据](https://tjjt.tongji.edu.cn/info/1101/9259.htm) | 仅入口快照 | 平台自身与主办同济官方活动报道对应；首页主要为应用标题，需实际HTTP正文检查是否JS壳。2026船舶OnSite是另一系列，不直接合并。 |
| 2026167 | 第二十一届全国大学生交通运输科技大赛 | B | [赛事站](http://www.nactrans.net/) · [依据](https://www.sues.edu.cn/7b/a5/c271a293797/page.htm) | 暂停 | 高校正式2026通知明确比赛官网nactrans.net，主办中国交通运输协会、承办北京建筑大学；本次HTTPS读取超时。第二十一届2026-05-23至24决赛已过，不标仍报名。 |
| 2026168 | 全国大学生轨道交通科技创新大赛 | B | [赛事站](https://www.nicrails.com/) · [依据](https://www.crs.org.cn/u/cms/www/202604/30160319gavk.pdf) | 部分读取成功：empty_or_javascript | 中国铁道学会官网申报书明确官网nicrails.com；2026首届7月17作品提交截止、8月28至30决赛已过。报名管理平台scrm.nicrails.com需要登录，公开官网可监测。 |
| 2026169 | 中国城市轨道交通科技创新创业大赛 | B | [校内官方通知](https://jtsyjxzx.tongji.edu.cn/23/1d/c34719a336669/page.htm) · [依据](https://www.bjtu.edu.cn/tzgg/162704.htm) | 读取失败：robots_unavailable | 同济共同主办及华东赛区主办官方首届2017通知；旧官网chinametro.net仅作历史线索，未验证仍归赛事方。不要与大学生轨道交通赛或2026中关村轨交创新创业赛混同。 |
| 2026170 | 口腔健康科普展示与交流活动 | B | [赛事站](https://www.shstomatology.org.cn/html/web/xinwendongtai/tongzhigonggao/index.html) · [依据](https://www.shstomatology.org.cn/html/web/xinwendongtai/tongzhigonggao/1922125798742921217.html) | 读取成功 | 上海市口腔医学会官方2023活动正式通知；网页显示2025-05-13为迁站日期，正文2023-09-15才投稿截止，不能误判2025或2026新赛。未核到2026届。 |
| 2026171 | 口腔形态技能大赛 | B | [校内官方通知](https://dent.tongji.edu.cn/info/1191/11879.htm) | 读取失败：robots_unavailable | 同济口腔医学院2026暑期交流营正式通知含口腔形态技能大赛；2026年8月活动，已结束；未确认独立赛事站。 |
| 2026172 | 壳牌汽车环保马拉松亚洲站 | B | [赛事站](https://www.shellecomarathon.com/) · [依据](https://www.shellecomarathon.com/programme/qatar.html) | 读取失败：empty_or_javascript | Shell Eco-marathon官方赛事站；2026卡塔尔站页面有正式规则。首页已出现2027亚太中东赛季，后续须按年份/赛区区分，不能沿用旧届日期。 |
| 2026173 | 中国大学生电动方程式大赛（2026） | B | [主办／承办方](https://www.sae-china.org/news/notices/202601/7199.html) | 读取成功 | 中国汽车工程学会2026蔚来杯电动方程式启动公告；2026报名已截止，不能按公告收录日当报名期。 |
| 2026174 | 中国大学生方程式汽车大赛（2026） | B | [主办／承办方](https://www.sae-china.org/news/notices/202601/7200.html) | 读取成功 | 中国汽车工程学会2026吉利杯方程式汽车大赛启动公告。赛事届次与电动/无人驾驶项目分开记录。 |
| 2026175 | 中国大学生无人驾驶方程式大赛（2026） | B | [赛事站](http://www.formulastudent.com.cn/) · [依据](https://img.sae-china.org/web/2026/01/%E4%B8%89%E5%8F%B7%E5%85%AC%E5%91%8A%281%29.pdf) | 部分读取成功：empty_or_javascript | 中国汽车工程学会2026无人驾驶方程式三号公告明确给出中国大学生方程式系列赛事官网；须限定无人驾驶赛项与2026届。 |
| 2026176 | 中国汽车工程学会巴哈大赛（2026） | B | [赛事站](https://www.bajasaechina.com/) · [依据](https://www.sae-china.org/meeting/meeting.php?id=392) | 读取成功 | 巴哈官方赛事站已有2026桐乡站公告；中国汽车工程学会官网也设该赛事介绍。 |
| 2026177 | 第十一届“汇创青春”——大学生文化创意作品展示活动（产品设计类） | B | [主办／承办方](https://www.shanghai.gov.cn/nw31406/20260624/fd83e6044f0c43178ad198bbb3073a83.html) | 仅入口快照 | 上海市政府2026年6月24日发布第十一届汇创青春优秀作品汇展，明确包含本目录对应类别；属于活动结果/汇展消息，不能作为仍征稿证据。需继续找该类别承办方征集原文。 |
| 2026178 | 第十一届“汇创青春”——大学生文化创意作品展示活动（视觉传达设计类） | B | [主办／承办方](https://www.shanghai.gov.cn/nw31406/20260624/fd83e6044f0c43178ad198bbb3073a83.html) | 仅入口快照 | 上海市政府2026年6月24日发布第十一届汇创青春优秀作品汇展，明确包含本目录对应类别；属于活动结果/汇展消息，不能作为仍征稿证据。需继续找该类别承办方征集原文。 |
| 2026179 | 戴森设计奖 | B | [赛事站](https://www.jamesdysonaward.org/zh-cn/home/) | 读取失败：robots_unavailable | 戴森设计奖官方中文站；2026时间表明确，报名7月15日结束。后续不能将下一年官网更新覆盖本届。 |
| 2026180 | 全球生物设计挑战赛（Bio Design Challenge） | B | [赛事站](https://www.biodesignchallenge.org/) · [依据](https://www.biodesignchallenge.org/2026) | 仅入口快照 | Biodesign Challenge官方站；2026专题与2027报名分别存在，2026峰会6月举行，已结束。 |
| 2026181 | 水晶客舱奖（Crystal Cabin Award） | B | [赛事站](https://www.crystal-cabin-award.com/) · [依据](https://www.crystal-cabin-award.com/participate) | 仅入口快照 | Crystal Cabin Award官方站；2026获奖/决赛信息与2027征集并存，须按年度拆分。 |
| 2026182 | 第十七届丘成桐大学生数学竞赛 | B | [赛事站](https://www.yau-contest.com/) · [依据](https://yau-contest.com/page-rule.html) | 读取成功 | 丘成桐大学生数学竞赛官网与规则页明确第十七届及2026年度。 |
| 2026183 | 美国大学生数学建模竞赛（2026） | B | [赛事站](https://www.contest.comap.com/undergraduate/contests/index.html) · [依据](https://www.contest.comap.com/undergraduate/contests/mcm/contests/2026/results/index.html) | 仅入口快照 | COMAP官方MCM/ICM入口；2026结果页已发布，首页出现2027时需保留届次区别。 |
| 2026184 | 全国大学生创新体验竞赛 | B | [赛事站](https://www.chinaccsis.com/data/list/cxtys) · [依据](https://www.chinaccsis.com/Data/View/966) | 读取成功 | 中国创造学会创新体验赛官方栏目，已发现第九届正式通知；该目录入口不等于当前开放报名。 |
| 2026185 | 国际大学生混凝土龙舟邀请赛 | B | [赛事站](https://www.concretedragon.org/) | 部分读取成功：empty_or_javascript | 赛事官网明确2026第八届由广西大学、西交利物浦大学主办，6月26—28日举行，已结束；正文可直接读取。 |
| 2026186 | 海峡两岸青少年创客大赛-结构挑战 | B | [校内官方通知](https://news.tongji.edu.cn/info/1002/91706.htm) | 读取失败：robots_unavailable | 同济主办方发布第十届海峡两岸青少年创客大赛报道，含结构挑战；往届已结束，未确认2026征集公告/独立站。 |
| 2026187 | 全国大学生“茅以升公益桥—小桥工程”创新设计大赛 | B | [主办／承办方](https://civil.bjtu.edu.cn/cms/item/23868.html) | 读取成功 | 联合主办方北京交通大学土建学院发布第七届茅以升公益桥—小桥工程赛事报道；往届消息，2026新届未确认。 |
| 2026188 | 全国大学生加筋挡土墙设计竞赛 | B | [待确认线索](https://chinatag.org.cn/uploads/soft/220107/1-22010G43P3.pdf) | 待确认 | 补查有中国土工合成材料工程协会chinatag.org.cn域名线索，但主页超时，尚未实读该站竞赛通知。公开记录多名为“全国大学生加筋土挡墙设计大赛”，目录名称措辞不同，且2026当届入口未核实，不接入聚合站npoall作为官方。 |
| 2026189 | 全国高等学校木结构设计竞赛 | B | [校内官方通知](https://structure.tongji.edu.cn/info/1004/7225.htm) | 读取失败：robots_unavailable | 同济建筑工程系发布第十届全国高等学校木结构设计竞赛决赛消息；往届已结束，2026新届未确认。 |
| 2026190 | 上海市大学生“创造杯”大赛 | B | [校内官方通知](https://civileng.tongji.edu.cn/bb/85/c18194a179077/page.htm) | 读取失败：robots_unavailable | 同济土木学院官方创造杯报道；仅确认历史举办，不代表2026仍举办或开放报名，需新通知。 |
| 2026191 | 世界大学生桥梁设计大赛 | B | [赛事站](https://www.wtc-conference.com/award/BDC/) · [依据](https://www.chts.cn/xs/TZGG/art/2026/art_4ba927087a724d6b998e56fc7725d06a.html) | 读取成功 | 世界交通运输大会桥梁设计赛官方栏目；中国公路学会有2026通知背书。 |
| 2026192 | “德语之星”全国高校德语演讲比赛 | B | [校内官方通知](https://deutsch.tongji.edu.cn/info/1041/1361.htm) | 读取失败：robots_unavailable | 同济德语系主办方第五届德语之星正式通知；应从该页继续核对届次和报名期限。 |
| 2026193 | “卡西欧杯”中国日语专业本科生·研究生演讲辩论大赛 | B | [主办／承办方](https://www.casio.com.cn/news/2025/05/20250525) | 仅入口快照 | 卡西欧主办方2025第十七届比赛报道；2026新公告未确认，不能把往届报道当报名通知。 |
| 2026194 | “人民中国杯”日语国际翻译大赛 | B | [赛事站](https://www.jpworld.cn/match/index) · [依据](https://www.jpworld.cn/match/article_detail/68) | 读取成功 | 日语世界网人民中国杯官方比赛入口；可读的第五届公告日期为2022年，2026届尚未确认。 |
| 2026195 | “外教社·词达人杯”全国大学生英语词汇能力大赛 | B | [主办／承办方](https://cclpps.shisu.edu.cn/_upload/article/files/e5/4f/e0f9bfe84c30b179d9c8fd88604a/877c1310-242e-42d5-9890-8c268c3f4b2f.pdf) · [依据](https://cclpps.shisu.edu.cn/) | 读取失败：unsupported_content | 已实读共同主办方上海外国语大学中国外语战略研究中心官网所载第二届章程，正文明确2022年，非2026现行细则；参赛及信息发布主要使用词达人/WExpress公众号。主页明确链接赛事专栏https://cclpps.shisu.edu.cn/qgdxsyychnlds/list.htm，但专栏此次读取失败，可由采集器复测；PDF为历史来源兜底。 |
| 2026196 | “扎雅杯”全国德语配音比赛 | B | [赛事站](https://peiyin.zhayadeutsch.cn/) | 读取失败：empty_or_javascript | 扎雅杯德语配音官方赛事站有2026第六届日程及组委会通知；同济德语系官网亦有该赛事获奖消息。 |
| 2026197 | 可持续发展全国青年德语风采大赛 | B | [主办／承办方](https://cdi.zust.edu.cn/info/1143/3301.htm) | 读取成功 | 2025联合主办方浙江科技大学中德学院第九届决赛报道；2026新届未确认。 |
| 2026198 | 全国大学生“用日语讲好中国故事”微视频大赛 | B | [主办／承办方](https://www.dhu.edu.cn/2024/1119/c7783a422711/pagem.htm) | 仅入口快照 | 主办方东华大学第四届2024用日语讲好中国故事微视频比赛报道；名称含全国高校日语专业，需保留目录别名，不视为2026征集。 |
| 2026199 | 全国大学生日语演讲比赛 | B | [主办／承办方](https://www.zjminghaojy.com/News/202412728.html) · [依据](https://wgyxy.zjhu.edu.cn/_upload/article/files/a1/5c/993f6f1c49ed8614fbf19386b429/048e48cc-3c0a-4cfc-9c44-007151b9d122.pdf) | 读取成功 | 联合主办方浙江明好教育发布第一届全国大学生日语演讲大赛暨第十五届浙江省赛通知；原通知落款浙江大学组委会。区别于中华全国日语演讲比赛；网页直开本次未成功，搜索索引可核标题/主办关系。 |
| 2026200 | 全国德语写作比赛 | B | [待确认线索](https://ogp.fudan.edu.cn/adlzx/list.htm) | 待确认 | 已实读复旦大学奥地利中心介绍，确认其与奥地利学术交流机构及上海总领馆文化处每年举办德语写作大赛；但未查到2026具体通知，也未充分证明目录“全国德语写作比赛”与该同名赛事的唯一对应关系，保留待确认，不以国才杯德语写作替代。 |
| 2026201 | 全国高校本科生德语配音大赛 | B | [主办／承办方](https://news.bfsu.edu.cn/article/318299/cate/4) | 仅入口快照 | 主办方北京外国语大学报道第八届全国高校本科生德语配音大赛2026年5月决赛；已结束。 |
| 2026202 | 全国高校德语专业本科生学术创新大赛 | B | [待确认线索](https://sfl.pku.edu.cn/xsyd/xwdt/69c90a4ed927430caf9f9d5695ef0ece.htm) | 待确认 | 补查多所参赛高校2026赛后报道一致指向浙江大学举办第六届（2026-05-16已结束），但未查到主办方可公开读取的当届章程或赛事专栏。参与高校报道只留线索，不作为主办方采集入口。 |
| 2026203 | 全国高校德语专业大学生德语辩论赛 | B | [主办／承办方](https://de.bfsu.edu.cn/info/1086/2690.htm) | 仅入口快照 | 联合主办方北京外国语大学德语学院第十三届2022比赛通知；历史正式入口，2026新届未确认。 |
| 2026204 | 全国医学英语词汇竞赛 | B | [主办／承办方](https://jwc.bbmu.edu.cn/info/1040/3256.htm) | 读取成功 | 承办方蚌埠医科大学教务处首届2021医学英语词汇竞赛通知；只确认历史官方公告，当前届次/报名平台待核。 |
| 2026205 | 上海市第二届学术英语演讲比赛 | B | [主办／承办方](https://cec.fudan.edu.cn/83/12/c23080a754450/page.htm) | 仅入口快照 | 主办方复旦大学发布2026春季第二届赛事通知；后续官方报道确认2026年4月18日决赛结束。 |
| 2026206 | 笹川杯全国高校日本知识大赛 | B | [赛事站](https://www.jss.or.jp/ch/itn/kouryu/) · [依据](https://www.jss.or.jp/ch/) | 部分读取成功：http_error | 日本科学协会中日共创未来项目官方栏目明确笹川杯全国高校日本知识大赛；还需当届征集通知，不能使用其他征文项目日期。 |
| 2026207 | 笹川杯日本研究论文大赛 | B | [赛事站](https://www.jss.or.jp/ch/itn/kouryu/sakubun/) | 部分读取成功：http_error | 日本科学协会官方栏目包含笹川杯日本研究论文大赛；同页还介绍品书知日本等项目，采集须按标题分段，不能混用日期。 |
| 2026208 | 亚太青年模拟APEC大会 | B | [赛事站](https://www.modelapec.com/) · [依据](https://www.modelapec.com/gywm) | 读取失败：empty_or_javascript | 亚太青年模拟APEC大会官网，其关于我们页说明主办体系；当届报名需另取正式通知。 |
| 2026209 | 中国大学生5分钟科研英语演讲大赛 | B | [主办／承办方](https://waiyu.sdust.edu.cn/info/1038/10362.htm) | 仅入口快照 | 2026承办方山东科技大学外国语学院发布第九届科研英语演讲赛事消息，主办中国学术英语教学研究会；属于已举行报道，目录中的5分钟名称须与正式规程对照。 |
| 2026210 | 中国人日语作文大赛 | B | [赛事站](http://duan.jp/jp/index.htm) · [依据](https://www.cn.emb-japan.go.jp/itpr_zh/11_000001_00106.html) | 暂停 | 已实读日本驻华大使馆2022第18届报道并确认其链接日本侨报社duan.jp；又实读主办方发行者TheDuanPress公开博客，明确第22届指向该竞赛入口。官网入口本次502/超时，不能从湖州等参赛高校校内4月截止推断2026全国截止。 |
| 2026211 | 中华全国日语演讲比赛 | B | [主办／承办方](https://www.ceaie.edu.cn/uploads/attached/file/20211220/C20853315159620.pdf) | 读取失败：unsupported_content | 中国教育国际交流协会第十七届正式通知原件；历史2021文件，不是2026报名通知。区别于浙江大学举办的全国大学生日语演讲大赛。 |
| 2026212 | 国际大学生物理竞赛（2026） | B | [赛事站](https://uphysicsc.com/) | 读取成功 | University Physics Competition官方站已出现2026赛事规则；以英语原文当届时间及时区为准。 |
| 2026213 | 全国部分地区大学生物理竞赛（上海赛区） | B | [校内官方通知](https://jwc.tongji.edu.cn/00/3b/c30359a327739/page.htm) | 读取失败：robots_unavailable | 同济本科生院发布上海市物理学会第39届2023参赛通知，明确校内报名入口；2026第42届原公告未确认。 |
| 2026214 | 中国大学生物理学术竞赛（2026） | B | [主办／承办方](https://physics.suda.edu.cn/db/3b/c1905a711483/page.htm) | 仅入口快照 | 2026全国赛承办方苏州大学物理学院正式报道：第十七届8月12—16日举办；已结束。cupt-iypt.com仅确认提供管理系统，不作为全国赛官网。 |
| 2026215 | 全国大学生智能技术应用大赛 | B | [主办／承办方](https://www.glmu.edu.cn/jwc/info/1242/6682.htm) | 仅入口快照 | 2026全国决赛承办高校桂林医科大学校选通知明确第八届全国赛10月在本校举行、主办中国医药教育协会；页面是校选规则，不能直接当全国报名规则。 |
| 2026216 | 医学虚拟仿真实验创新大赛 | B | [校内官方通知](https://med.tongji.edu.cn/info/1322/7908.htm) | 读取失败：robots_unavailable | 同济医学院官方首届医学虚拟仿真实验创新大赛报道，2022历史信息；未确认独立官网或2026新届。 |
| 2026217 | “半夏的纪念”北京国际大学生影像展 | B | [主办／承办方](https://tvs.cuc.edu.cn/2023/0306/c240a202526/page.htm) | 仅入口快照 | 主办方中国传媒大学电视学院第20届2023半夏的纪念征片通知；历史入口，2026届需重新核对。 |
| 2026218 | “国青杯”高校艺术设计作品展评 | B | [主办／承办方](https://www.clsedu.org.cn/h/news/tzgg/2024-08-26/1970.html) | 读取成功 | 主办中国人生科学学会2024国青杯高校艺术设计作品征集正式通知；尚未确认2026原公告。 |
| 2026219 | 第十一届“汇创青春”——大学生文化创意作品展示活动（数媒、动画类） | B | [主办／承办方](https://www.shanghai.gov.cn/nw31406/20260624/fd83e6044f0c43178ad198bbb3073a83.html) | 仅入口快照 | 上海市政府2026年6月24日发布第十一届汇创青春优秀作品汇展，明确包含本目录对应类别；属于活动结果/汇展消息，不能作为仍征稿证据。需继续找该类别承办方征集原文。 |
| 2026220 | ACP世界大赛 | B | [赛事站](https://www.acpwcc.com/portal/index.html) | 仅入口快照 | Adobe Certified Professional世界大赛中国赛区官方运营入口，首页明确由ACP中国运营管理中心组织；不能自动等同国际总决赛报名入口。 |
| 2026221 | 白玉兰国际音乐节 | B | [赛事站](https://m.cn-imc.com/match_zc.asp?matchID=2A8I28L2KI) · [依据](https://www.cn-imc.com/matchZC-29CW6BPY7J.html) | 读取失败：robots_unavailable | 已实读承办方华夏璇音官方2023年白玉兰国际音乐节国乐竞演章程，主办方为上海视觉艺术学院；初赛报名2023-05-01至06-25、决赛2023-08-06至08-10，均历史。仅已核实国乐单元，不能冒充覆盖声乐/钢琴等全部单元及2026征集。 |
| 2026222 | 北京国际电影节“游戏•动漫•电影单元”高校动画短片、漫画作品评选 | B | [赛事站](https://www.bjiff.com/xghd/xqdy/kmlt/202512/t20251224_188579_ext.html) | 仅入口快照 | 已实读电影节官网第十六届游戏·动漫·电影单元高校作品征集，动画/漫画/绘本均明列，非AIGC单元；页面发布时间2025-12-03，报名截止2025-12-30，终评2026年3月，已过期；不得按URL路径日期代替正文日期。 |
| 2026223 | 第十一届“汇创青春”——大学生文化创意作品展示活动（戏剧舞蹈类） | B | [主办／承办方](https://www.shanghai.gov.cn/nw31406/20260624/fd83e6044f0c43178ad198bbb3073a83.html) | 仅入口快照 | 上海市政府2026年6月24日发布第十一届汇创青春优秀作品汇展，明确包含本目录对应类别；属于活动结果/汇展消息，不能作为仍征稿证据。需继续找该类别承办方征集原文。 |
| 2026224 | 第十一届“汇创青春”——大学生文化创意作品展示活动（音乐艺术类） | B | [主办／承办方](https://www.shanghai.gov.cn/nw31406/20260624/fd83e6044f0c43178ad198bbb3073a83.html) | 仅入口快照 | 上海市政府2026年6月24日发布第十一届汇创青春优秀作品汇展，明确包含本目录对应类别；属于活动结果/汇展消息，不能作为仍征稿证据。需继续找该类别承办方征集原文。 |
| 2026225 | 第十一届“汇创青春”——大学生文化创意作品展示活动（综合类（影视）） | B | [主办／承办方](https://www.shanghai.gov.cn/nw31406/20260624/fd83e6044f0c43178ad198bbb3073a83.html) | 仅入口快照 | 上海市政府2026年6月24日发布第十一届汇创青春优秀作品汇展，明确包含本目录对应类别；属于活动结果/汇展消息，不能作为仍征稿证据。需继续找该类别承办方征集原文。 |
| 2026226 | 法国巴黎音乐艺术大赛 | B | [待确认线索](https://www.jfdaily.com/sgh/detail?id=1719354) | 待确认 | 补查媒体和参赛高校材料使用PMAC/CIMAP，指向SAE艺术教育平台，但尚无经实读核验的组委会/主办方独立官网与2026正式规则；不按英文近似名猜域名或自动认作其他巴黎音乐比赛。 |
| 2026227 | 华为影像 · 金鸡手机电影计划 | B | [赛事站](https://www.cgrhfff.com/forum/mobile-image-project/) · [依据](https://www.cgrhfff.com/news-center/33322/) | 仅入口快照 | 中国金鸡百花电影节官网手机影像计划栏目，含金鸡手机电影计划正式征集；按届次确认华为合作名称变化。 |
| 2026228 | 金犊奖国际竞赛 | B | [赛事站](https://www.ad-young.com/) · [依据](https://www.ad-young.com/WebMethod/GetHomePageTopYear) | 仅入口快照 | 金犊奖官方入口，页面显示金犊35载，官方接口返回2026年度资料；部分正文由JavaScript加载。 |
| 2026229 | 蓝桥杯大赛视觉艺术设计赛 | B | [赛事站](https://design.lanqiao.cn/) · [依据](https://design.lanqiao.cn/connect-us) | 读取失败：empty_or_javascript | 蓝桥杯视觉艺术设计赛独立官方子站；页面依赖JavaScript，联系方式页可检索，后续需正式接口/公告适配。 |
| 2026230 | 李斯特国际青少年钢琴大赛 | B | [赛事站](https://franzliszt.com.cn/) · [依据](https://www.franzliszt.com.cn/col.jsp?id=127) | 读取失败：robots_unavailable | 李斯特国际青少年钢琴大赛官方中文门户有第七届栏目与欧中文化艺术交流协会信息；本次直开缓存未命中，后续抓取需复核可达性及届次。 |
| 2026231 | 睿抗机器人开发者大赛CAIA数字文化创意赛道 | B | [赛事站](https://www.raicom.com.cn/) · [依据](https://jiaowc.sbs.edu.cn/bmgg/89fe53e4ff7548e1a7f10f67cbf40c77.htm) | 读取成功 | 睿抗赛事官方门户；高校2025CAIA通知给出此官网，网页主要由JavaScript加载。须筛出CAIA数字文化创意而非机器人其他赛道。 |
| 2026232 | 上海大学生国际广告节 | B | [主办／承办方](https://www.shu.edu.cn/info/1056/399325.htm) | 仅入口快照 | 上海大学发布第25届2026上海国际大学生广告节启幕通知；目录名称词序不同。勿混同面向广告行业的上海国际广告节。 |
| 2026233 | 中国大学生创意节 | B | [赛事站](https://www.ccfcs.cn/index/pages/yxs) · [依据](https://edu.sh.gov.cn/xxgk2_zdgz_qtjy_03/20241010/3e28c324ea274d30b10c6a58c6ccbf9e.html) | 部分读取成功：empty_or_javascript | 中国大学生创意节官方项目页，上海市教委有第六届活动通知；主页本次访问超时，项目页面能被检索，2026征集待确认。 |
| 2026234 | 中国大学生广告艺术节学院奖 | B | [赛事站](https://www.5iidea.com/) · [依据](https://sam.xatu.edu.cn/info/14948/198147.htm) | 读取失败：empty_or_javascript | 学院奖创意星球官方赛事平台，高校2026通知给出此地址；页面由JavaScript加载，应按春秋季/赛题分别取公告。 |
| 2026235 | 中国高等院校影视协会年度推优暨“学院奖”大赛 | B | [赛事站](https://www.ccava.cn/tyhd) · [依据](https://www.ccava.cn/xhgl) | 读取失败：empty_or_javascript | 中国高校影视学会推优活动官方栏目；目录称协会，主办方称学会，官方记载2019起学院奖调整为影视作品推优活动，需保留别名。 |
| 2026236 | 中国国际动漫节“金猴奖” | B | [赛事站](https://jhj.cicaf.com/) · [依据](https://cicaf.hzxcw.gov.cn/content/content_49249.html) | 读取成功 | 中国国际动漫节金猴奖官方专站；动漫节官方2026公告可作为当前届次证据。 |
| 2026237 | 中国品牌设计大赛 | B | [主办／承办方](https://yichuanxueyuan.xdsisu.edu.cn/2628/list.htm) · [依据](https://yichuanxueyuan.xdsisu.edu.cn/2025/0507/c2724a51865/page.htm) | 读取成功 | 承办院校上外贤达学院将中国品牌设计大赛列入主办赛事栏目，并公布第三届颁奖/第四届启动；暂未确认独立赛事官网及2026新届。 |
| 2026238 | 中国青少年音乐比赛•蜂鸟音乐奖 | B | [赛事站](https://www.china-ymc.cn/) | 读取失败：robots_unavailable | 中国青少年音乐比赛蜂鸟音乐奖官网；核查当届年龄分组和参赛日期后再收录具体年度赛事。 |
| 2026239 | 中国数据新闻大赛 | B | [赛事站](http://www.cdjcow.com/) · [依据](https://journal.whu.edu.cn/20240720qsaz) | 读取成功 | 联合主办方武汉大学2024第九届通知明确指定该大赛官网；本次网站直开失败，作为已证实但可达性待复核入口，不能声称已接入自动采集。 |
| 2026240 | 博睿杯“我是外交官”全国大学生外交风采大赛 | B | [主办／承办方](https://nanyang.xmu.edu.cn/info/1019/38271.htm) | 仅入口快照 | 主办方厦门大学南洋研究院发布第十六届博睿杯决赛消息；已结束的比赛报道，后续需本届/下届正式征集。 |
| 2026241 | 全国土木工程材料作品设计大赛 | C | [校内官方通知](https://dcem.tongji.edu.cn/info/1062/2320.htm) | 读取失败：robots_unavailable | 同济土木工程材料系主办方第八届2023作品设计创意赛报道；赛事名称存在作品设计/设计创意等表述，2026新届需核对。 |
| 2026242 | 上海市土木工程材料知识竞赛 | C | [校内官方通知](https://polymer.tongji.edu.cn/__local/D/50/94/EAF6228AAC76F3CC03FF762EAB5_A37EE8C3_46AB3.pdf) | 读取失败：robots_unavailable | 同济材料学院主办的第九届城建星材杯正式通知原件；同届官方报道为2024，不依据搜索显示的近期抓取日期当2026公告。 |
| 2026243 | 第14届同济大学应用力学创新竞赛 | C | [校内官方通知](https://aero-mech.tongji.edu.cn/aa/6c/c3354a43628/page.htm) | 读取失败：robots_unavailable | 主办学院第五届应用力学创新竞赛正式规则；仅能确认历史官网来源，尚未找到目录指定第14届原始公告，禁止复用第五届赛题/日期。 |
| 2026244 | 同济大学化学知识竞赛 | C | [校内官方通知](https://chemweb.tongji.edu.cn/info/1517/15553.htm) | 读取失败：robots_unavailable | 同济化学学院第十八届国药杯化学知识竞赛报道，活动2025年12月6日；2026新届通知待发布/核查。 |
| 2026245 | “建环杯”人工环境健康度智能诊断竞赛 | C | [待确认线索](https://mefaculty.tongji.edu.cn/index/xyxw/113.htm) | 待确认 | 已实读同济机械学院官方历史新闻列表，找到2021第一届“建环杯”新生科技竞赛；详情https://mefaculty.tongji.edu.cn/info/1022/1654.htm读取失败，尚不能确认与目录“人工环境健康度智能诊断”赛题相同，故不强行匹配。 |
| 2026246 | 济时开讲 | C | [校内官方通知](https://my.tongji.edu.cn/info/1003/5309.htm) | 读取失败：robots_unavailable | 同济马克思主义学院2026第五届济时开讲决赛报道，6月2日发布；已结束，不作为开放报名。 |
| 2026247 | 使命与担当 | C | [校内官方通知](https://my.tongji.edu.cn/info/1003/4671.htm) | 读取失败：robots_unavailable | 同济马克思主义学院第十届使命与担当社会实践与创新竞赛官方报道；历史赛事，2026最新通知未确认。 |
| 2026248 | “学院杯”中国室内与环境设计大赛 | C | [赛事站](https://www.xueyuanbei.com/) | 读取成功 | 学院杯中国室内与环境设计大赛官方站，显示组委会和中国室内装饰协会支持信息；可直接读取赛事资讯。 |
| 2026249 | 中国设计智造奖 | C | [赛事站](https://www.di-award.org/zh) · [依据](https://www.di-award.org/zh/rules.html) | 读取成功 | 中国设计智造大奖官方站，2026规则及初评消息明确；不同报名通道截止日期不同，不得取单一日期覆盖所有通道。 |
| 2026250 | 上海市大学生日语才能演示大赛 | C | [赛事站](https://www.ieas.net.cn/) · [依据](https://www.ieas.net.cn/upload/files/2025/2/%E4%B8%8A%E6%B5%B7%E6%95%99%E8%82%B2%E5%9B%BD%E9%99%85%E4%BA%A4%E6%B5%81%E5%8D%8F%E4%BC%9A%E9%A1%B9%E7%9B%AE%E4%B8%8E%E6%9C%8D%E5%8A%A1%E6%89%8B%E5%86%8C%EF%BC%882025%EF%BC%89.pdf) | 读取成功 | 联合主办上海教育国际交流协会官方2025项目手册明确赛事由原日语演讲比赛更名；赛事专页/2026安排待核。 |
| 2026251 | 同济大学新生德语能力竞赛 | C | [校内官方通知](https://deutsch.tongji.edu.cn/xwzx/xwsd.htm) | 读取失败：robots_unavailable | 同济德语系新闻列表明确2026第六届新生德语能力竞赛5月23日、6月3日举行，6月20日报道；已结束，列表具体文章链接需后续提取。 |
| 2026252 | 同济大学创新物理实验设计竞赛（2026） | C | [校内官方通知](https://mphylab.tongji.edu.cn/page/home/info23362_INFO) | 读取失败：robots_unavailable | 同济物理实验中心官方2024第五届获奖公示；确认主办网站但未检索到2026原始通知，禁止把2024第五届改写成2026。 |
| 2026253 | 同济大学医学院2026年医学生临床综合技能竞赛 | C | [校内官方通知](https://news.tongji.edu.cn/info/1003/50938.htm) | 读取失败：robots_unavailable | 同济官方2015—2016学年临床综合技能竞赛报道；仅历史入口，目录指定2026届详细通知尚未确认。 |
| 2026254 | “卓越杯”全球治理与中国方案——青年国际胜任力案例设计大赛 | C | [主办／承办方](https://info.shisu.edu.cn/aa/96/c177a43670/page.htm) | 仅入口快照 | 主办上海外国语大学发布第三届2025卓越杯全球治理与中国方案青年案例赛报道；2026第四届新公告未确认。 |
| 2026255 | “汇川杯”全国智能自动化创新大赛 | C | [赛事站](https://icup.inovance.com/) · [依据](https://icup.inovance.com/guide/index) | 部分读取成功：empty_or_javascript | 汇川技术官方域名下全国智能自动化创新大赛网站，当前第三届资料；inocup.inovance.com亦为官方赛事系统，后续须按届次取规则。 |

## 后续处理

1. 优先修复可读官方通知对应的通知列表和标题别名，复查失败入口；不先扩大目录范围。
2. 为近期有报名通知的赛事逐项补字段适配器，尤其处理PDF/Word附件、校赛截止与国赛截止差别。
3. 后续AI仅辅助提取和解释，输出需带原文依据并校验届次、资格、人数、时间；关键缺项不自动发布。
4. 前端维持当前／历史分组，未知时间如实提示；数据库保留旧正文、赛事与队伍历史。

操作命令见[采集发现](competition-discovery.md)，团队状态见[进度](progress.md)。
