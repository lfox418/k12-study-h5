-- ============================================================================
-- K12 英语分级背词 + 初中数学每日三题 双科学习系统 SQLite 建表与初始化脚本
-- 数据库文件: k12_study.db
-- 并发优化: WAL 模式 + synchronous=NORMAL + busy_timeout=5000
-- ============================================================================

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- 1. 用户档案表（6位推荐码即唯一身份 ID，多端隔离）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    referral_code   TEXT PRIMARY KEY,              -- 6位数字/字母推荐码（统一大写）
    phone           TEXT DEFAULT NULL,             -- 11位中国大陆手机号（免验证码直绑）
    total_points    INTEGER NOT NULL DEFAULT 0 CHECK (total_points >= 0),
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ----------------------------------------------------------------------------
-- 2. 英语多学段分级基础词库表
--    grade_stage: 'primary' | 'grade_7' | 'grade_8' | 'grade_9'
--    examples: JSON 字符串数组，如 [{"en":"...","zh":"..."}]
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS english_words (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    grade_stage     TEXT NOT NULL CHECK (grade_stage IN ('primary', 'grade_7', 'grade_8', 'grade_9')),
    word            TEXT NOT NULL,
    phonetic        TEXT NOT NULL DEFAULT '',
    meaning         TEXT NOT NULL,
    examples        TEXT NOT NULL DEFAULT '[]',    -- JSON array
    source          TEXT NOT NULL DEFAULT 'builtin',
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(grade_stage, word)
);
CREATE INDEX IF NOT EXISTS idx_english_words_stage ON english_words(grade_stage);

-- ----------------------------------------------------------------------------
-- 3. 英语三阶动态掌握度状态机表
--    mastery_level: 1(新词/一级) | 2(巩固词/二级) | 3(熟练词/三级)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_english_progress (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    referral_code   TEXT NOT NULL,
    word_id         INTEGER NOT NULL,
    mastery_level   INTEGER NOT NULL DEFAULT 1 CHECK (mastery_level IN (1, 2, 3)),
    streak          INTEGER NOT NULL DEFAULT 0,    -- 连续全对次数，>=3 晋升三级
    wrong_count     INTEGER NOT NULL DEFAULT 0,
    last_reviewed_at TEXT DEFAULT NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(referral_code, word_id),
    FOREIGN KEY (referral_code) REFERENCES users(referral_code) ON DELETE CASCADE,
    FOREIGN KEY (word_id) REFERENCES english_words(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_uep_user_level ON user_english_progress(referral_code, mastery_level);

-- ----------------------------------------------------------------------------
-- 4. 初中数学分年级典型题库表
--    grade: 'grade_7' | 'grade_8' | 'grade_9'
--    question_type: 'choice' (选择题) | 'fill' (填空题)
--    options: JSON 字符串数组，填空题为 '[]'
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS math_questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    grade           TEXT NOT NULL CHECK (grade IN ('grade_7', 'grade_8', 'grade_9')),
    topic_tag       TEXT NOT NULL,
    question_type   TEXT NOT NULL DEFAULT 'choice' CHECK (question_type IN ('choice', 'fill')),
    stem            TEXT NOT NULL,                 -- 支持 LaTeX 公式
    options         TEXT NOT NULL DEFAULT '[]',    -- JSON array, 如 ["A. ...", "B. ..."]
    answer          TEXT NOT NULL,                 -- 标答（选择题如 "A"，填空题支持多等价写法用 | 分隔）
    analysis        TEXT NOT NULL,                 -- 支持 LaTeX 分步解析
    content_hash    TEXT NOT NULL UNIQUE,          -- 标准化题干 SHA-256 去重键
    source          TEXT NOT NULL DEFAULT 'builtin',
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_math_questions_grade ON math_questions(grade);

-- ----------------------------------------------------------------------------
-- 5. 数学做题进度与错题本表
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_math_progress (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    referral_code   TEXT NOT NULL,
    question_id     INTEGER NOT NULL,
    attempt_count   INTEGER NOT NULL DEFAULT 0,
    correct_count   INTEGER NOT NULL DEFAULT 0,
    wrong_count     INTEGER NOT NULL DEFAULT 0,
    is_in_wrong_book INTEGER NOT NULL DEFAULT 0,   -- 1=在错题本中
    last_wrong_answer TEXT DEFAULT NULL,
    last_attempted_at TEXT DEFAULT NULL,
    UNIQUE(referral_code, question_id),
    FOREIGN KEY (referral_code) REFERENCES users(referral_code) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES math_questions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ump_user_wrong ON user_math_progress(referral_code, is_in_wrong_book);

-- ----------------------------------------------------------------------------
-- 6. 全科目共享学习批次表（核心统一引擎）
--    subject: 'english' | 'math'
--    status: 'in_progress' | 'passed' | 'expired'
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS study_sessions (
    id              TEXT PRIMARY KEY,              -- UUID
    referral_code   TEXT NOT NULL,
    subject         TEXT NOT NULL CHECK (subject IN ('english', 'math')),
    stage_or_grade  TEXT NOT NULL,                 -- primary/grade_7/grade_8/grade_9
    item_ids        TEXT NOT NULL,                 -- JSON array of word_id or question_id
    first_wrong_ids TEXT NOT NULL DEFAULT '[]',    -- JSON array: 首次提交时答错的条目 ID（用于个人中心标红）
    latest_wrong_ids TEXT NOT NULL DEFAULT '[]',   -- JSON array: 最近一次提交答错的条目 ID
    attempt_count   INTEGER NOT NULL DEFAULT 0,    -- 本轮已提交校验次数（含错题重学）
    status          TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'passed', 'expired')),
    started_at      INTEGER NOT NULL,              -- Unix 秒级时间戳
    expires_at      INTEGER NOT NULL,              -- started_at + 1800 (严格 30 分钟)
    completed_at    INTEGER DEFAULT NULL,          -- 通关或作废时间戳
    duration_sec    INTEGER DEFAULT NULL,          -- 耗时（秒）
    total_score_delta INTEGER NOT NULL DEFAULT 0,  -- 本轮累计净积分变动
    daily_bonus_awarded INTEGER NOT NULL DEFAULT 0,-- 本轮是否发放了每日+5分奖励
    created_date    TEXT NOT NULL,                 -- 自然日 YYYY-MM-DD
    FOREIGN KEY (referral_code) REFERENCES users(referral_code) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sessions_user_sub ON study_sessions(referral_code, subject, started_at DESC);

-- ----------------------------------------------------------------------------
-- 7. 每日通关 +5 分奖励防重表（每个自然日、每科目仅发放一次）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_pass_rewards (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    referral_code   TEXT NOT NULL,
    subject         TEXT NOT NULL CHECK (subject IN ('english', 'math')),
    reward_date     TEXT NOT NULL,                 -- YYYY-MM-DD
    session_id      TEXT NOT NULL,
    points          INTEGER NOT NULL DEFAULT 5,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(referral_code, subject, reward_date),
    FOREIGN KEY (referral_code) REFERENCES users(referral_code) ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- 8. 积分变动流水表（审计与可追溯）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS point_ledger (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    referral_code   TEXT NOT NULL,
    session_id      TEXT DEFAULT NULL,
    subject         TEXT NOT NULL,
    delta           INTEGER NOT NULL,
    balance_after   INTEGER NOT NULL CHECK (balance_after >= 0),
    reason          TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (referral_code) REFERENCES users(referral_code) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ledger_user ON point_ledger(referral_code, id DESC);

-- ----------------------------------------------------------------------------
-- 9. 定时增量同步日志表（每 6 小时任务记录）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type        TEXT NOT NULL,                 -- 'english_sync' | 'math_sync' | 'full_sync'
    added_count     INTEGER NOT NULL DEFAULT 0,
    skipped_count   INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'success',
    detail          TEXT DEFAULT '',
    started_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    finished_at     TEXT DEFAULT NULL
);

-- ============================================================================
-- 预制初始化数据：测试推荐码
-- ============================================================================
INSERT OR IGNORE INTO users (referral_code, phone, total_points) VALUES
('K12001', '13800138000', 0),
('K12002', NULL, 0),
('STU888', NULL, 0),
('VIP666', NULL, 0);

-- ============================================================================
-- 预制初始化词库：英语四学段（每学段 12 词，共 48 词，开箱即满 10 词/轮）
-- ============================================================================

-- 1) 小学 600 必备词 (primary)
INSERT OR IGNORE INTO english_words (grade_stage, word, phonetic, meaning, examples) VALUES
('primary', 'apple', '/ˈæp.əl/', 'n. 苹果', '[{"en":"She eats a fresh apple every morning.","zh":"她每天早上吃一个新鲜的苹果。"},{"en":"Would you like some apple juice?","zh":"你想喝点苹果汁吗？"}]'),
('primary', 'library', '/ˈlaɪ.brər.i/', 'n. 图书馆', '[{"en":"We must keep quiet in the school library.","zh":"我们在学校图书馆里必须保持安静。"},{"en":"I borrowed two storybooks from the library.","zh":"我从图书馆借了两本故事书。"}]'),
('primary', 'weather', '/ˈweð.ər/', 'n. 天气', '[{"en":"What is the weather like today?","zh":"今天天气怎么样？"},{"en":"The weather is warm and sunny in spring.","zh":"春天的天气温暖又晴朗。"}]'),
('primary', 'breakfast', '/ˈbrek.fəst/', 'n. 早餐', '[{"en":"I usually have milk and bread for breakfast.","zh":"我早餐通常喝牛奶、吃面包。"}]'),
('primary', 'bicycle', '/ˈbaɪ.sɪ.kəl/', 'n. 自行车', '[{"en":"He rides his bicycle to school every day.","zh":"他每天骑自行车去上学。"}]'),
('primary', 'hospital', '/ˈhɒs.pɪ.təl/', 'n. 医院', '[{"en":"My aunt works as a nurse in a big hospital.","zh":"我阿姨在一家大医院当护士。"}]'),
('primary', 'elephant', '/ˈel.ɪ.fənt/', 'n. 大象', '[{"en":"The elephant has a long trunk and big ears.","zh":"大象有长长的鼻子和大大耳朵。"}]'),
('primary', 'umbrella', '/ʌmˈbrel.ə/', 'n. 雨伞', '[{"en":"Take an umbrella with you because it may rain.","zh":"带把伞吧，因为可能会下雨。"}]'),
('primary', 'classroom', '/ˈklɑːs.ruːm/', 'n. 教室', '[{"en":"Our classroom is bright and clean.","zh":"我们的教室明亮又整洁。"}]'),
('primary', 'favorite', '/ˈfeɪ.vər.ɪt/', 'adj. 最喜欢的；n. 特别喜爱的人或物', '[{"en":"Blue is my favorite color.","zh":"蓝色是我最喜欢的颜色。"}]'),
('primary', 'festival', '/ˈfes.tɪ.vəl/', 'n. 节日', '[{"en":"The Spring Festival is very important in China.","zh":"春节在中国非常重要。"}]'),
('primary', 'homework', '/ˈhəʊm.wɜːk/', 'n. 家庭作业', '[{"en":"Please finish your homework before dinner.","zh":"请在晚饭前完成家庭作业。"}]');

-- 2) 初一核心词 (grade_7)
INSERT OR IGNORE INTO english_words (grade_stage, word, phonetic, meaning, examples) VALUES
('grade_7', 'improve', '/ɪmˈpruːv/', 'v. 提高；改善', '[{"en":"Reading every day helps you improve your English.","zh":"每天阅读有助于提高你的英语水平。"}]'),
('grade_7', 'describe', '/dɪˈskraɪb/', 'v. 描述；形容', '[{"en":"Can you describe what the lost dog looks like?","zh":"你能描述一下那只走丢的狗长什么样吗？"}]'),
('grade_7', 'practice', '/ˈpræk.tɪs/', 'v. & n. 练习；实践', '[{"en":"She practices playing the piano for an hour daily.","zh":"她每天练习弹钢琴一小时。"}]'),
('grade_7', 'friendly', '/ˈfrend.li/', 'adj. 友好的', '[{"en":"Our new classmates are very friendly to us.","zh":"我们的新同学对我们非常友好。"}]'),
('grade_7', 'remember', '/rɪˈmem.bər/', 'v. 记住；记得', '[{"en":"Remember to turn off the lights when you leave.","zh":"离开时记得关灯。"}]'),
('grade_7', 'important', '/ɪmˈpɔː.tənt/', 'adj. 重要的', '[{"en":"It is important to get enough sleep every night.","zh":"每晚保证充足的睡眠很重要。"}]'),
('grade_7', 'different', '/ˈdɪf.ər.ənt/', 'adj. 不同的', '[{"en":"People in different countries have different habits.","zh":"不同国家的人有不同的习惯。"}]'),
('grade_7', 'delicious', '/dɪˈlɪʃ.əs/', 'adj. 美味的', '[{"en":"The dumplings made by my grandma are delicious.","zh":"奶奶包的饺子非常美味。"}]'),
('grade_7', 'relaxing', '/rɪˈlæk.sɪŋ/', 'adj. 令人放松的', '[{"en":"Listening to soft music is very relaxing.","zh":"听轻音乐非常令人放松。"}]'),
('grade_7', 'museum', '/mjuːˈziː.əm/', 'n. 博物馆', '[{"en":"We visited the science museum last weekend.","zh":"我们上周末参观了科技博物馆。"}]'),
('grade_7', 'vacation', '/veɪˈkeɪ.ʃən/', 'n. 假期', '[{"en":"Where did you go during the summer vacation?","zh":"你暑假去了哪里？"}]'),
('grade_7', 'popular', '/ˈpɒp.jə.lər/', 'adj. 受欢迎的；流行的', '[{"en":"Basketball is very popular among middle school students.","zh":"篮球在中学生中非常受欢迎。"}]');

-- 3) 初二核心词 (grade_8)
INSERT OR IGNORE INTO english_words (grade_stage, word, phonetic, meaning, examples) VALUES
('grade_8', 'encourage', '/ɪnˈkʌr.ɪdʒ/', 'v. 鼓励；激励', '[{"en":"My math teacher always encourages me to try harder.","zh":"我的数学老师总是鼓励我更加努力。"}]'),
('grade_8', 'challenge', '/ˈtʃæl.ɪndʒ/', 'n. & v. 挑战', '[{"en":"Climbing that mountain was a real challenge for us.","zh":"攀登那座山对我们来说是一次真正的挑战。"}]'),
('grade_8', 'communicate', '/kəˈmjuː.nɪ.keɪt/', 'v. 交流；沟通', '[{"en":"It is helpful to communicate openly with your parents.","zh":"与父母坦诚沟通很有帮助。"}]'),
('grade_8', 'environment', '/ɪnˈvaɪ.rən.mənt/', 'n. 环境', '[{"en":"Everyone should play a part in protecting the environment.","zh":"每个人都应该为保护环境贡献一份力量。"}]'),
('grade_8', 'independent', '/ˌɪn.dɪˈpen.dənt/', 'adj. 独立的；自主的', '[{"en":"Doing chores helps children become more independent.","zh":"做家务有助于孩子变得更加独立。"}]'),
('grade_8', 'experience', '/ɪkˈspɪə.ri.əns/', 'n. 经验；经历；v. 体验', '[{"en":"Volunteering at the shelter was an unforgettable experience.","zh":"在收容所当志愿者是一次难忘的经历。"}]'),
('grade_8', 'traditional', '/trəˈdɪʃ.ən.əl/', 'adj. 传统的', '[{"en":"Paper cutting is a traditional Chinese art form.","zh":"剪纸是一种中国传统艺术形式。"}]'),
('grade_8', 'necessary', '/ˈnes.ə.sər.i/', 'adj. 必要的；必需的', '[{"en":"Water and air are necessary for all living things.","zh":"水和空气对所有生物都是必需的。"}]'),
('grade_8', 'achieve', '/əˈtʃiːv/', 'v. 达到；实现', '[{"en":"Work hard and you will achieve your dream.","zh":"努力奋斗，你就会实现梦想。"}]'),
('grade_8', 'progress', '/ˈprəʊ.ɡres/', 'n. 进步；进展', '[{"en":"He has made great progress in physics this term.","zh":"他这学期在物理方面取得了很大进步。"}]'),
('grade_8', 'condition', '/kənˈdɪʃ.ən/', 'n. 条件；状况', '[{"en":"The plants grow well under good light conditions.","zh":"这些植物在良好的光照条件下生长得很好。"}]'),
('grade_8', 'pressure', '/ˈpreʃ.ər/', 'n. 压力', '[{"en":"Doing sports is a healthy way to reduce study pressure.","zh":"运动是减轻学习压力的健康方式。"}]');

-- 4) 初三中考核心词 (grade_9)
INSERT OR IGNORE INTO english_words (grade_stage, word, phonetic, meaning, examples) VALUES
('grade_9', 'influence', '/ˈɪn.flu.əns/', 'n. & v. 影响', '[{"en":"Good books can have a lifelong influence on young people.","zh":"好书能对年轻人产生终生的影响。"}]'),
('grade_9', 'congratulate', '/kənˈɡrætʃ.ə.leɪt/', 'v. 祝贺；恭喜', '[{"en":"We all congratulated her on winning the first prize.","zh":"我们都祝贺她获得一等奖。"}]'),
('grade_9', 'responsible', '/rɪˈspɒn.sə.bəl/', 'adj. 有责任心的；负责的', '[{"en":"Teenagers should learn to be responsible for their choices.","zh":"青少年应该学会对自己的选择负责。"}]'),
('grade_9', 'opportunity', '/ˌɒp.əˈtjuː.nə.ti/', 'n. 机会；时机', '[{"en":"This competition gave me a valuable opportunity to grow.","zh":"这次比赛给了我一次宝贵的成长机会。"}]'),
('grade_9', 'scientific', '/ˌsaɪ.ənˈtɪf.ɪk/', 'adj. 科学的', '[{"en":"We need scientific methods to solve this problem.","zh":"我们需要科学的方法来解决这个问题。"}]'),
('grade_9', 'overcome', '/ˌəʊ.vəˈkʌm/', 'v. 克服；战胜', '[{"en":"With courage and patience, we can overcome any difficulty.","zh":"凭借勇气和耐心，我们能克服任何困难。"}]'),
('grade_9', 'discover', '/dɪˈskʌv.ər/', 'v. 发现；发觉', '[{"en":"Scientists hope to discover new sources of clean energy.","zh":"科学家们希望能发现新的清洁能源。"}]'),
('grade_9', 'advantage', '/ədˈvɑːn.tɪdʒ/', 'n. 优点；优势', '[{"en":"Speaking two languages is a big advantage in the future.","zh":"会说两种语言在未来是一大优势。"}]'),
('grade_9', 'creative', '/kriˈeɪ.tɪv/', 'adj. 有创造力的', '[{"en":"She came up with a creative solution to the puzzle.","zh":"她想出了一个解决这道难题的创意方案。"}]'),
('grade_9', 'gradually', '/ˈɡrædʒ.u.ə.li/', 'adv. 逐渐地；逐步地', '[{"en":"The fog gradually disappeared as the sun rose.","zh":"随着太阳升起，雾气逐渐消散了。"}]'),
('grade_9', 'valuable', '/ˈvæl.jə.bəl/', 'adj. 贵重的；有价值的', '[{"en":"Thank you for giving me such valuable advice.","zh":"谢谢你给我如此宝贵的建议。"}]'),
('grade_9', 'separate', '/ˈsep.ər.eɪt/', 'v. 分开；adj. 单独的', '[{"en":"Please separate recyclable waste from kitchen waste.","zh":"请将可回收垃圾与厨余垃圾分开。"}]');

-- ============================================================================
-- 预制初始化题库：初中数学三年级高频典型题（每级 8 题，共 24 题，覆盖全部 12 类核心考点）
-- ============================================================================

-- ---------------- 初一 (grade_7) ----------------
INSERT OR IGNORE INTO math_questions (grade, topic_tag, question_type, stem, options, answer, analysis, content_hash) VALUES
(
    'grade_7', '有理数混合运算', 'choice',
    '计算：$$(-2)^3 + (-3) \times \left[(-4)^2 + 2\right] - (-3)^2 \div (-2)$$ 的值为（  ）',
    '["A. -57.5", "B. -53.5", "C. -66.5", "D. -49.5"]',
    'A',
    '第一步：先算乘方，$(-2)^3 = -8$，$(-4)^2 = 16$，$(-3)^2 = 9$。\n第二步：算中括号内，$16 + 2 = 18$。\n第三步：算乘除，$(-3) \times 18 = -54$，$9 \div (-2) = -4.5$。\n第四步：算加减，$-8 + (-54) - (-4.5) = -62 + 4.5 = -57.5$。\n故正确答案为 **A**。',
    'g7_rational_01'
),
(
    'grade_7', '有理数混合运算', 'fill',
    '已知 $|a - 2| + (b + 3)^2 = 0$，则 $(a + b)^{2025}$ 的值为 ________。',
    '[]',
    '-1',
    '因为绝对值与平方数均具有非负性，即 $|a - 2| \ge 0$ 且 $(b + 3)^2 \ge 0$。\n由和为 $0$ 可得：$a - 2 = 0$ 且 $b + 3 = 0$，解得 $a = 2, b = -3$。\n代入得 $a + b = 2 + (-3) = -1$。\n因此 $(a + b)^{2025} = (-1)^{2025} = -1$。',
    'g7_rational_02'
),
(
    'grade_7', '整式加减与化简求值', 'choice',
    '先化简多项式 $2(x^2y + xy) - 3(x^2y - xy) - 4x^2y$，再求当 $x = -1, y = 2$ 时的值是（  ）',
    '["A. -20", "B. -10", "C. 0", "D. -18"]',
    'A',
    '第一步：去括号得 $2x^2y + 2xy - 3x^2y + 3xy - 4x^2y$。\n第二步：合并同类项得 $(2 - 3 - 4)x^2y + (2 + 3)xy = -5x^2y + 5xy$。\n第三步：代入 $x = -1, y = 2$：\n原式 $= -5 \times (-1)^2 \times 2 + 5 \times (-1) \times 2 = -10 - 10 = -20$。\n故正确答案为 **A**。',
    'g7_poly_01'
),
(
    'grade_7', '整式加减与化简求值', 'fill',
    '若单项式 $3x^{m+1}y^4$ 与 $-2x^3y^{2n}$ 是同类项，则 $m^n$ 的值为 ________。',
    '[]',
    '4',
    '由同类项定义，相同字母的指数相等：\n$m + 1 = 3 \Rightarrow m = 2$；\n$2n = 4 \Rightarrow n = 2$。\n因此 $m^n = 2^2 = 4$。',
    'g7_poly_02'
),
(
    'grade_7', '一元一次方程应用题', 'choice',
    '某商品按进价提高 $40\%$ 后标价，再打八折销售，结果仍获利 $15$ 元。设该商品进价为 $x$ 元，则可列方程为（  ）',
    '["A. 0.8(1 + 40\\%)x - x = 15", "B. 0.8 \\times 40\\%x - x = 15", "C. (1 + 40\\%)x - 0.8x = 15", "D. 0.8(1 + 40\\%)x = 15"]',
    'A',
    '进价为 $x$ 元，提高 $40\%$ 后的标价为 $(1 + 40\%)x$ 元。\n打八折后的实际售价为 $0.8(1 + 40\%)x$ 元。\n根据“利润 = 售价 - 进价”，可得方程：$0.8(1 + 40\%)x - x = 15$（解得 $x = 125$）。\n故正确答案为 **A**。',
    'g7_eq_01'
),
(
    'grade_7', '一元一次方程应用题', 'fill',
    '甲、乙两车分别从相距 $360\text{ km}$ 的 A、B 两地同时出发相向而行，甲车速度为 $65\text{ km/h}$，乙车速度为 $55\text{ km/h}$，经过 ________ 小时两车相遇。',
    '[]',
    '3',
    '设经过 $t$ 小时两车相遇。\n根据相遇问题路程关系：$65t + 55t = 360$。\n合并同类项得 $120t = 360$，解得 $t = 3$（小时）。',
    'g7_eq_02'
),
(
    'grade_7', '线段与角的动态计算', 'choice',
    '已知线段 $AB = 10\text{ cm}$，点 $C$ 在直线 $AB$ 上，且 $BC = 4\text{ cm}$，$M$ 是线段 $AC$ 的中点，则线段 $AM$ 的长为（  ）',
    '["A. 3 cm", "B. 7 cm", "C. 3 cm 或 7 cm", "D. 5 cm"]',
    'C',
    '注意题目条件是“点 $C$ 在**直线** $AB$ 上”，需分两种情况讨论：\n情况一：点 $C$ 在线段 $AB$ 上时，$AC = AB - BC = 10 - 4 = 6\text{ cm}$，故 $AM = \frac{1}{2}AC = 3\text{ cm}$。\n情况二：点 $C$ 在线段 $AB$ 的延长线上时，$AC = AB + BC = 10 + 4 = 14\text{ cm}$，故 $AM = \frac{1}{2}AC = 7\text{ cm}$。\n综上，$AM$ 的长为 $3\text{ cm}$ 或 $7\text{ cm}$，选 **C**。',
    'g7_geo_01'
),
(
    'grade_7', '线段与角的动态计算', 'fill',
    '已知 $\angle AOB = 80^\circ$，射线 $OC$ 在 $\angle AOB$ 内部，且 $\angle AOC = 30^\circ$，$OM$ 平分 $\angle BOC$，则 $\angle AOM =$ ________ 度。（只填数字）',
    '[]',
    '55',
    '因为 $OC$ 在 $\angle AOB$ 内部，所以 $\angle BOC = \angle AOB - \angle AOC = 80^\circ - 30^\circ = 50^\circ$。\n又因为 $OM$ 平分 $\angle BOC$，所以 $\angle COM = \frac{1}{2}\angle BOC = 25^\circ$。\n因此 $\angle AOM = \angle AOC + \angle COM = 30^\circ + 25^\circ = 55^\circ$。',
    'g7_geo_02'
);

-- ---------------- 初二 (grade_8) ----------------
INSERT OR IGNORE INTO math_questions (grade, topic_tag, question_type, stem, options, answer, analysis, content_hash) VALUES
(
    'grade_8', '全等三角形判定与辅助线', 'choice',
    '如图，在 $\triangle ABC$ 和 $\triangle DEF$ 中，已知 $AB = DE$，$\angle B = \angle E$，若添加下列条件之一，仍**不能**判定 $\triangle ABC \cong \triangle DEF$ 的是（  ）',
    '["A. BC = EF", "B. \\angle A = \\angle D", "C. \\angle C = \\angle F", "D. AC = DF"]',
    'D',
    '逐项检验全等三角形判定定理：\n- 添加 $BC = EF$，满足 **SAS**；\n- 添加 $\angle A = \angle D$，满足 **ASA**；\n- 添加 $\angle C = \angle F$，满足 **AAS**；\n- 添加 $AC = DF$，构成 **SSA**（边边角），不能保证两三角形全等。\n故正确答案为 **D**。',
    'g8_cong_01'
),
(
    'grade_8', '全等三角形判定与辅助线', 'fill',
    '在 $\triangle ABC$ 中，$AB = 6$，$AC = 4$，$AD$ 是 $BC$ 边上的中线，通过“倍长中线”法可求得中线 $AD$ 的取值范围为 $m < AD < n$，则 $m + n =$ ________。',
    '[]',
    '6',
    '【倍长中线辅助线】延长 $AD$ 至点 $E$，使 $DE = AD$，连接 $CE$。\n易证 $\triangle ABD \cong \triangle ECD$（SAS），故 $CE = AB = 6$。\n在 $\triangle ACE$ 中，由三角形三边关系：$CE - AC < AE < CE + AC$，即 $6 - 4 < 2AD < 6 + 4 \Rightarrow 2 < 2AD < 10$。\n解得 $1 < AD < 5$，故 $m = 1, n = 5$，$m + n = 6$。',
    'g8_cong_02'
),
(
    'grade_8', '轴对称与等腰三角形', 'choice',
    '已知等腰三角形的一个内角为 $50^\circ$，则这个等腰三角形的顶角度数为（  ）',
    '["A. 50^\\circ", "B. 80^\\circ", "C. 50^\\circ \\text{ 或 } 80^\\circ", "D. 65^\\circ"]',
    'C',
    '需分类讨论 $50^\circ$ 是顶角还是底角：\n- 若 $50^\circ$ 为顶角，则两底角均为 $\frac{180^\circ - 50^\circ}{2} = 65^\circ$，成立；\n- 若 $50^\circ$ 为底角，则顶角为 $180^\circ - 2 \times 50^\circ = 80^\circ$，成立。\n因此顶角为 $50^\circ$ 或 $80^\circ$，选 **C**。',
    'g8_iso_01'
),
(
    'grade_8', '轴对称与等腰三角形', 'fill',
    '在平面直角坐标系中，点 $P(3, -2)$ 关于 $y$ 轴对称的点的坐标是 $(-3, a)$，则 $a =$ ________。',
    '[]',
    '-2',
    '关于 $y$ 轴对称的两个点，横坐标互为相反数，纵坐标保持不变。\n点 $P(3, -2)$ 关于 $y$ 轴的对称点为 $(-3, -2)$，因此 $a = -2$。',
    'g8_iso_02'
),
(
    'grade_8', '因式分解与分式方程', 'choice',
    '解分式方程 $\dfrac{2}{x - 1} + \dfrac{x + 2}{1 - x} = 3$，其根的情况是（  ）',
    '["A. x = 1", "B. x = 0", "C. x = -\\frac{1}{2}", "D. 原方程无解"]',
    'C',
    '第一步：将 $1 - x$ 变形为 $-(x - 1)$，方程化为 $\dfrac{2 - (x + 2)}{x - 1} = 3$，即 $\dfrac{-x}{x - 1} = 3$。\n第二步：两边同乘 $(x - 1)$ 得 $-x = 3(x - 1) \Rightarrow -x = 3x - 3 \Rightarrow 4x = 3$？注意核对：\n重新检查分子：$2 - (x + 2) = -x$；$-x = 3x - 3 \Rightarrow 4x = 3 \Rightarrow x = \frac{3}{4}$。\n等等，若原题为 $\dfrac{1}{x - 1} + \dfrac{x + 2}{1 - x} = 3$ 呢？让我们改回精确无误的标准题：$-x = 3(x-1)$ 解为 $3/4$。此处修正选项与方程，确保 100% 严密。',
    'g8_frac_01_placeholder'
),
(
    'grade_8', '因式分解与分式方程', 'fill',
    '若关于 $x$ 的分式方程 $\dfrac{m}{x - 2} = \dfrac{1 - x}{2 - x} - 3$ 有增根，则实数 $m$ 的值为 ________。',
    '[]',
    '1',
    '第一步：方程两边同乘最简公分母 $(x - 2)$，得 $m = -(1 - x) - 3(x - 2)$。\n化简得 $m = x - 1 - 3x + 6 = -2x + 5$。\n第二步：因为方程有增根，增根必使分母为 $0$，即 $x - 2 = 0 \Rightarrow x = 2$。\n第三步：将 $x = 2$ 代入整式方程得 $m = -2 \times 2 + 5 = 1$。',
    'g8_frac_02'
),
(
    'grade_8', '一次函数图像与性质', 'choice',
    '已知一次函数 $y = (k - 2)x + k$ 的图像经过第一、二、四象限，则 $k$ 的取值范围是（  ）',
    '["A. k > 2", "B. 0 < k < 2", "C. k < 0", "D. k < 2"]',
    'B',
    '一次函数 $y = ax + b$ 经过第一、二、四象限的充要条件是斜率 $a < 0$ 且截距 $b > 0$。\n由此列不等式组：$\begin{cases} k - 2 < 0 \\ k > 0 \end{cases}$，解得 $0 < k < 2$。\n故正确答案为 **B**。',
    'g8_linear_01'
),
(
    'grade_8', '一次函数图像与性质', 'fill',
    '将直线 $y = 2x - 1$ 向上平移 $4$ 个单位长度后，所得直线与 $y$ 轴的交点纵坐标为 ________。',
    '[]',
    '3',
    '根据“上加下减”的平移规律，直线 $y = 2x - 1$ 向上平移 $4$ 个单位后得到 $y = 2x - 1 + 4 = 2x + 3$。\n令 $x = 0$，得与 $y$ 轴交点纵坐标为 $3$。',
    'g8_linear_02'
);

-- 修正 g8_frac_01_placeholder 为 100% 严密的分式方程题
DELETE FROM math_questions WHERE content_hash = 'g8_frac_01_placeholder';
INSERT OR IGNORE INTO math_questions (grade, topic_tag, question_type, stem, options, answer, analysis, content_hash) VALUES
(
    'grade_8', '因式分解与分式方程', 'choice',
    '把多项式 $2x^3 - 8x$ 在实数范围内分解因式，结果完全正确的是（  ）',
    '["A. 2x(x^2 - 4)", "B. 2x(x + 2)(x - 2)", "C. 2x(x - 2)^2", "D. x(2x + 4)(x - 2)"]',
    'B',
    '第一步：先提取公因式 $2x$，得 $2x^3 - 8x = 2x(x^2 - 4)$。\n第二步：再对 $x^2 - 4$ 运用平方差公式分解，得 $2x(x + 2)(x - 2)$。\n因式分解必须分解到不能再分解为止，故正确答案为 **B**。',
    'g8_frac_01'
);

-- ---------------- 初三 (grade_9) ----------------
INSERT OR IGNORE INTO math_questions (grade, topic_tag, question_type, stem, options, answer, analysis, content_hash) VALUES
(
    'grade_9', '一元二次方程根与系数', 'choice',
    '已知 $x_1, x_2$ 是一元二次方程 $x^2 - 5x + 3 = 0$ 的两个实数根，则 $x_1^2 + x_2^2$ 的值为（  ）',
    '["A. 19", "B. 25", "C. 22", "D. 31"]',
    'A',
    '先检验判别式：$\Delta = (-5)^2 - 4 \times 1 \times 3 = 13 > 0$，方程有两个不等实根。\n由韦达定理得：$x_1 + x_2 = 5$，$x_1 x_2 = 3$。\n利用完全平方变形：$x_1^2 + x_2^2 = (x_1 + x_2)^2 - 2x_1 x_2 = 5^2 - 2 \times 3 = 25 - 6 = 19$。\n故正确答案为 **A**。',
    'g9_quad_01'
),
(
    'grade_9', '一元二次方程根与系数', 'fill',
    '若关于 $x$ 的一元二次方程 $x^2 - 2x + k = 0$ 有两个相等的实数根，则 $k =$ ________。',
    '[]',
    '1',
    '方程有两个相等的实数根，等价于判别式 $\Delta = 0$。\n即 $(-2)^2 - 4 \times 1 \times k = 0 \Rightarrow 4 - 4k = 0 \Rightarrow k = 1$。',
    'g9_quad_02'
),
(
    'grade_9', '二次函数最值与综合', 'choice',
    '二次函数 $y = -x^2 + 4x + 1$ 在闭区间 $0 \le x \le 3$ 上的最大值与最小值分别是（  ）',
    '["A. 最大值 5，最小值 1", "B. 最大值 5，最小值 4", "C. 最大值 4，最小值 1", "D. 最大值 5，最小值 0"]',
    'A',
    '第一步：配方得 $y = -(x - 2)^2 + 5$，抛物线开口向下，对称轴为 $x = 2$。\n第二步：因为 $x = 2$ 在区间 $[0, 3]$ 内，所以当 $x = 2$ 时取得最大值 $y_{\max} = 5$。\n第三步：比较区间端点距离对称轴远近：$|0 - 2| = 2 > |3 - 2| = 1$，故在 $x = 0$ 处取得最小值 $y_{\min} = 1$。\n故正确答案为 **A**。',
    'g9_parabola_01'
),
(
    'grade_9', '二次函数最值与综合', 'fill',
    '将抛物线 $y = 2x^2$ 向右平移 $3$ 个单位，再向下平移 $1$ 个单位，所得新抛物线的顶点坐标为 $(h, k)$，则 $h + k =$ ________。',
    '[]',
    '2',
    '根据“左加右减、上加下减”平移规律，新抛物线解析式为 $y = 2(x - 3)^2 - 1$。\n其顶点坐标为 $(3, -1)$，故 $h = 3, k = -1$，$h + k = 2$。',
    'g9_parabola_02'
),
(
    'grade_9', '圆的切线与圆周角', 'choice',
    '已知 $AB$ 是 $\odot O$ 的直径，点 $C$ 在 $\odot O$ 上（不与 $A, B$ 重合），若 $\angle ABC = 35^\circ$，则 $\angle BAC$ 的度数为（  ）',
    '["A. 35^\\circ", "B. 55^\\circ", "C. 65^\\circ", "D. 70^\\circ"]',
    'B',
    '因为 $AB$ 是 $\odot O$ 的直径，根据“直径所对的圆周角是直角”，得 $\angle ACB = 90^\circ$。\n在 $\text{Rt}\triangle ABC$ 中，$\angle BAC = 90^\circ - \angle ABC = 90^\circ - 35^\circ = 55^\circ$。\n故正确答案为 **B**。',
    'g9_circle_01'
),
(
    'grade_9', '圆的切线与圆周角', 'fill',
    '从圆外一点 $P$ 引 $\odot O$ 的切线 $PA$，切点为 $A$，已知 $\odot O$ 的半径 $OA = 5$，$OP = 13$，则切线长 $PA =$ ________。',
    '[]',
    '12',
    '由切线性质定理可知 $OA \perp PA$，即 $\triangle OAP$ 为直角三角形，斜边为 $OP = 13$。\n由勾股定理：$PA = \sqrt{OP^2 - OA^2} = \sqrt{13^2 - 5^2} = \sqrt{144} = 12$。',
    'g9_circle_02'
),
(
    'grade_9', '相似三角形与锐角三角函数', 'choice',
    '在 $\text{Rt}\triangle ABC$ 中，$\angle C = 90^\circ$，若 $\sin A = \dfrac{3}{5}$，则 $\tan A$ 的值为（  ）',
    '["A. \\dfrac{4}{5}", "B. \\dfrac{3}{4}", "C. \\dfrac{4}{3}", "D. \\dfrac{5}{4}"]',
    'B',
    '设 $\angle A$ 的对边 $a = 3k$，斜边 $c = 5k$（$k > 0$）。\n由勾股定理得邻边 $b = \sqrt{c^2 - a^2} = 4k$。\n因此 $\tan A = \dfrac{a}{b} = \dfrac{3k}{4k} = \dfrac{3}{4}$。\n故正确答案为 **B**。',
    'g9_sim_01'
),
(
    'grade_9', '相似三角形与锐角三角函数', 'fill',
    '已知 $\triangle ABC \sim \triangle A''B''C''$，相似比为 $2 : 3$，若 $\triangle ABC$ 的面积为 $12$，则 $\triangle A''B''C''$ 的面积为 ________。',
    '[]',
    '27',
    '相似三角形的面积比等于相似比的平方。\n即 $\dfrac{S_{\triangle ABC}}{S_{\triangle A''B''C''}} = \left(\dfrac{2}{3}\right)^2 = \dfrac{4}{9}$。\n代入 $S_{\triangle ABC} = 12$，得 $S_{\triangle A''B''C''} = 12 \times \dfrac{9}{4} = 27$。',
    'g9_sim_02'
);
