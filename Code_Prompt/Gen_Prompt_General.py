
#==================================================
# ds_prompt.ipynb -- 构建提问模板
#==================================================

from datetime import datetime, timedelta
import itertools

# ========== 0. 复盘区间计算函数 ==========
def get_default_review_period():
    """
    获取默认复盘区间：本周周一至当日
    返回格式：2026年6月8日 – 2026年6月12日
    """
    today = datetime.now()
    # 计算本周周一（weekday(): 周一=0, 周日=6）
    monday = today - timedelta(days=today.weekday())
    
    # 格式化日期
    def format_date(date):
        return date.strftime("%Y年%m月%d日")
    
    return f"{format_date(monday)} – {format_date(today)}"

def get_custom_review_period(start_date, end_date):
    """
    获取自定义复盘区间
    参数:
        start_date: 开始日期，datetime对象或字符串"YYYY-MM-DD"
        end_date: 结束日期，datetime对象或字符串"YYYY-MM-DD"
    返回格式：2026年6月5日 – 2026年6月12日
    """
    def parse_date(date_input):
        if isinstance(date_input, str):
            return datetime.strptime(date_input, "%Y-%m-%d")
        return date_input
    
    def format_date(date):
        return date.strftime("%Y年%m月%d日")
    
    start = parse_date(start_date)
    end = parse_date(end_date)
    return f"{format_date(start)} – {format_date(end)}"

# ========== 1. 生成按公司分组的问题（支持复盘区间） ==========
def generate_queries_grouped_by_company(ticker_dict_list, questions, review_period=None):
    """
    根据股票字典和问题模板生成实际提问，并按公司分组
    参数:
        ticker_dict_list: 股票字典列表
        questions: 问题模板列表，支持占位符 {} 和 {period}
        review_period: 复盘区间字符串，如 "2026年6月5日 – 6月12日"，默认为None（将自动计算周一至当日）
    返回:
        列表，每个元素为 (company_id, questions_list) 的元组
    """
    # 如果未提供复盘区间，自动计算周一至当日
    if review_period is None:
        review_period = get_default_review_period()
    
    grouped_queries = []
    for stock in ticker_dict_list:
        company_id = f"{stock['name']} ({stock['ticker']})"
        company_questions = []
        for question_template in questions:
            # 先替换公司占位符
            actual_question = question_template.replace("{}", company_id)
            # 如果有复盘区间且模板中包含{period}占位符，则替换
            if "{period}" in actual_question:
                actual_question = actual_question.replace("{period}", review_period)
            company_questions.append(actual_question)
        grouped_queries.append((company_id, company_questions))
    return grouped_queries, review_period

def generate_queries_grouped_by_question(ticker_dict_list, questions, review_period=None):
    """
    根据股票字典和问题模板生成实际提问，并按问题类型分组
    参数:
        ticker_dict_list: 股票字典列表
        questions: 问题模板列表
        review_period: 复盘区间字符串，默认为None（将自动计算周一至当日）
    返回:
        问题列表，每组问题后添加一个空行作为分隔
    """
    # 如果未提供复盘区间，自动计算周一至当日
    if review_period is None:
        review_period = get_default_review_period()
    
    generated_queries = []
    for question_idx, question_template in enumerate(questions):
        for stock in ticker_dict_list:
            stock_id = f"{stock['name']} ({stock['ticker']})"
            actual_question = question_template.replace("{}", stock_id)
            if "{period}" in actual_question:
                actual_question = actual_question.replace("{period}", review_period)
            generated_queries.append(actual_question)
        if question_idx < len(questions) - 1:
            generated_queries.append("")
    return generated_queries

# ========== 2. 生成特定公司对的比较分析提问 ==========
def resolve_company_pair(key_a, key_b, ticker_data):
    """
    根据公司名称或ticker从ticker_data中查找完整标识（name (ticker)）
    :param key_a: 公司A的name或ticker
    :param key_b: 公司B的name或ticker
    :param ticker_data: 股票字典列表
    :return: (company_a_str, company_b_str)
    """
    def find_company(key):
        for stock in ticker_data:
            if key == stock['name'] or key == stock['ticker']:
                return f"{stock['name']} ({stock['ticker']})"
        return None
    company_a = find_company(key_a)
    company_b = find_company(key_b)
    if company_a is None or company_b is None:
        raise ValueError(f"找不到公司: {key_a} 或 {key_b}")
    return company_a, company_b

def generate_comparison_queries_from_pairs(comparison_pairs, comparison_template, ticker_data, review_period=None):
    """
    根据指定的公司对列表生成比较提问
    :param comparison_pairs: 列表，每个元素为 (公司A的name或ticker, 公司B的name或ticker)
    :param comparison_template: 比较提问模板，包含两个{}占位符
    :param ticker_data: 股票字典列表
    :param review_period: 复盘区间字符串，默认为None（将自动计算周一至当日）
    :return: 比较提问列表
    """
    # 如果未提供复盘区间，自动计算周一至当日
    if review_period is None:
        review_period = get_default_review_period()
    
    queries = []
    for key_a, key_b in comparison_pairs:
        company_a, company_b = resolve_company_pair(key_a, key_b, ticker_data)
        query = comparison_template.format(company_a, company_b)
        if "{period}" in query:
            query = query.replace("{period}", review_period)
        queries.append(query)
    return queries

# ========== 3. 打印函数（包含比较部分） ==========
def print_queries(grouped_queries, other_queries, comparison_queries, ticker_data, question_templates, review_period=None):
    """打印问题列表到控制台，包含比较分析部分"""
    print("="*60)
    print(f"复盘区间: {review_period if review_period else get_default_review_period()}")
    print("="*60)
    print()
    
    print("按公司分组的问题列表:\n")
    for company_id, questions in grouped_queries:
        print(f"将上面输出文本转换成可下载的web文档。\n")
        print(f"将上面最新的2个对话的输出文本转换成可下载的web文档。\n")
        print(f"对{company_id}的下列问题的解答进行归纳和总结：")
        for idx, question in enumerate(questions, 1):
            # 高亮显示包含复盘区间的问题
            if review_period and review_period in question:
                print(f"问题{idx}: {question} 【复盘区间：{review_period}】")
            else:
                print(f"问题{idx}: {question}")
        print()

    print("\n" + "="*50 + "\n")

    print("其他提问:")
    print("对下列问题的解答进行归纳和总结：")
    for idx, query in enumerate(other_queries, 1):
        print(f"问题{idx}: {query}")

    if comparison_queries:
        print("\n" + "="*50 + "\n")
        print("公司两两比较分析提问:")
        print(f"将上面输出文本转换成可下载的web文档。\n")
        print(f"将上面最新的2个对话的输出文本转换成可下载的web文档。\n")
        print("对下列比较分析问题进行解答：")
        for idx, query in enumerate(comparison_queries, 1):
            print("\n" + "="*3)
            print(f"比较{idx}: {query}")

    total_company = sum(len(q) for _, q in grouped_queries)
    print(f"\n统计信息:")
    print(f"- 公司数量: {len(ticker_data)}")
    print(f"- 问题模板数量: {len(question_templates)}")
    print(f"- 按公司分组生成的问题总数: {total_company}")
    print(f"- 其他问题数量: {len(other_queries)}")
    print(f"- 公司比较提问数量: {len(comparison_queries)}")
    print(f"- 总问题数量: {total_company + len(other_queries) + len(comparison_queries)}")
    print(f"- 复盘区间: {review_period if review_period else get_default_review_period()}")

# ========== 4. 保存到文件函数（包含比较部分） ==========
def save_queries_to_file(filepath, grouped_queries, other_queries, comparison_queries, ticker_data, question_templates, review_period=None):
    """将生成的问题列表保存到文本文件，包含比较分析部分"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("AI分析问题列表\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            if review_period:
                f.write(f"复盘区间: {review_period}\n")
            f.write("=" * 60 + "\n\n")

            total_company = sum(len(q) for _, q in grouped_queries)
            f.write("【统计信息】\n")
            f.write(f"- 公司数量: {len(ticker_data)}\n")
            f.write(f"- 问题模板数量: {len(question_templates)}\n")
            f.write(f"- 按公司分组生成的问题总数: {total_company}\n")
            f.write(f"- 其他问题数量: {len(other_queries)}\n")
            f.write(f"- 公司比较提问数量: {len(comparison_queries)}\n")
            f.write(f"- 总问题数量: {total_company + len(other_queries) + len(comparison_queries)}\n")
            if review_period:
                f.write(f"- 复盘区间: {review_period}\n")
            f.write("\n")

            # 第一部分：按公司分组
            f.write("=" * 60 + "\n")
            f.write("第一部分：按公司分组的问题\n")
            f.write("=" * 60 + "\n\n")
            for company_id, questions in grouped_queries:
                f.write(f"将上面输出文本转换成可下载的web文档。\n")
                f.write(f"将上面最新的2个对话的输出文本转换成可下载的web文档。\n\n")
                f.write(f"对{company_id}的下列问题的解答进行归纳和总结：\n")
                for idx, question in enumerate(questions, 1):
                    f.write(f"问题{idx}: {question}\n")
                f.write("\n")

            # 第二部分：其他宏观和市场问题
            f.write("=" * 60 + "\n")
            f.write("第二部分：其他宏观和市场问题\n")
            f.write("=" * 60 + "\n\n")
            f.write("对下列问题的解答进行归纳和总结：\n")
            for idx, query in enumerate(other_queries, 1):
                f.write(f"问题{idx}: {query}\n")
            f.write("\n")

            # 第三部分：公司两两比较分析问题
            if comparison_queries:
                f.write("=" * 60 + "\n")
                f.write("第三部分：公司两两比较分析问题\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"将上面输出文本转换成可下载的web文档。\n")
                f.write(f"将上面最新的2个对话的输出文本转换成可下载的web文档。\n\n")
                f.write("对下列比较分析问题进行解答：\n")
                for idx, query in enumerate(comparison_queries, 1):
                    f.write("\n" + "="*3 +"\n")
                    f.write(f"比较{idx}: {query}\n")
                f.write("\n")

            # 附录一：股票列表
            f.write("=" * 60 + "\n")
            f.write("附录一：股票列表\n")
            f.write("=" * 60 + "\n\n")
            for i, stock in enumerate(ticker_data, 1):
                f.write(f"{i:2d}. {stock['name']} ({stock['ticker']})\n")

            # 附录二：单公司问题模板
            f.write("\n" + "=" * 60 + "\n")
            f.write("附录二：问题模板（单公司）\n")
            f.write("=" * 60 + "\n\n")
            for i, template in enumerate(question_templates, 1):
                f.write(f"{i:2d}. {template}\n")

            # 附录三：公司比较分析模板
            f.write("\n" + "=" * 60 + "\n")
            f.write("附录三：公司比较分析模板\n")
            f.write("=" * 60 + "\n\n")
            f.write("1. 对{}与{}进行多维度比较分析，包括企业战略转型，企业核心竞争力，盈利质量及可持续性，未来3年盈利预测，估值提升，股东回报措施，以及技术分析层面确认股价处于中长期上升通道，或者震荡筑底，或者中长期下降通道，根据2025年财报，计算每股净值（港元）及市净率，ROE及其它等关键财务指标等。\n")

        print(f"✓ 问题列表已成功保存到: {filepath}")
        return True
    except Exception as e:
        print(f"✗ 保存文件时出错: {e}")
        return False

# ===================== 主程序 =====================
if __name__ == "__main__":
    # ---------- 配置参数 ----------
    # 复盘区间配置（设为None则自动计算周一至当日）
    REVIEW_PERIOD = None  # 自动计算本周周一至当日
    
    # 如果需要自定义区间，可以使用以下方式：
    # REVIEW_PERIOD = get_custom_review_period("2026-06-05", "2026-06-12")
    # 或者直接设置字符串：
    # REVIEW_PERIOD = "2026年6月5日 – 2026年6月12日"
    
    # 也可以为不同股票设置不同区间（高级用法示例）
    # 如果需要为特定股票设置不同区间，可以在生成后手动修改
    
    # 修改问题模板，添加{period}占位符支持复盘区间
    question_templates = [
        "\n*** A 技术分析 ***",
        "对{}近日走势进行复盘分析，复盘区间：{period}",  # 修改后的问题2，自动添加区间信息
        "分析{}技术形态",
        "分析{}关键价位:支撑位2，支撑位1，阻力位1，阻力位2",
        "计算{}的实际流通股本及关键价位:支撑位2，支撑位1，阻力位1，阻力位2",
        "对{}进行技术分析评估，其综合动力评分是多少？基于量化模型计算的结果。量化模型对价格趋势、成交量、资金流向、超买超卖、波动率、市场情绪、机构动力、宏观、形态等多个维度进行加权评分",
        "分析{}赔率、胜率有哪些特点？", 
        "分析{}股价是否已经完成反转？",  
        "分析{}短期、中期、长期关键阻力与支撑价位",   
        "分析{}是否已进入上升通道？",
        "分析{}是否已进入下降通道？",
        "采用牛市三阶段理论分析{}",
        "采用波浪理论分析{}",
        "采用缠论分析{}的关键买点与卖点",
        
        "\n*** B 基本面分析 ***",
        "{}是真低估还是存在估值陷阱？",
        "对{}进行8维度综合动力评分，包括1.趋势结构，（价格与估值，均线系统）. 2. 动量指标RSI/MACD, 3.成交量与量价关系，4.支撑与阻力强度，5.资金流向（机构与散户对战），沽空数据，6.筹码结构稀缺性。7. 基本面/债务/评级催化。8.宏观与技术共振。",
        "对于{}，如何从企业战略转型，企业核心竞争力，盈利质量及可持续性，未来3年盈利预测，估值提升，股东回报措施，以及技术分析层面确认股价处于中长期上升通道，或者震荡筑底，或者中长期下降通道？根据2025年财报，计算每股净值（港元）及市净率，ROE及其它等关键财务指标。",
        "分析{}短期、中期、长期关键阻力与支撑价位， 赔率及胜率，利空利多消息，采用分析波浪理论{}中长期趋势，制定一个基于“猎人模式”的投资策略以及基于“农夫模式”的投资策略。",  
        "从政策底、市场底、业绩底、资金底等角度分析{}，并进行确认和交叉验证，详细解释如何捕捉具备持续上涨潜力的困境反转个股，以及如何完整参与其估值修复与盈利增长的全过程?",
        "分析{}2026年Q1财报",
        "分析{}的盈利质量， 以及与同行业相比有哪些优势和劣势",
        "基于基本面持续改善，{}是否进入中长期上升通道？",    
        "未来3-5年，{}的盈利质量预计会达到什么水平？",
        "分析{}自由现金流改善的可持续性如何？具体有哪些量化指标可以跟踪验证？",    
        "未来3-5年{}ROE目标是多少？",
        "分析{}有哪些核心竞争力？",
        "分析{}盈利与估值双升的潜力",
        "对{}按照高分红股票标准进行深度评估，包括这6个维度:1.股息收益率（TTM）。2.派息比率合理性。3.自由现金流覆盖倍数。4.分红成长性与持续性。5.防御性估值保护。6.潜在风险。",
        "对{}按照高成长性股票标准深度评估",
        "**分析{}的财报风险点和估值逻辑",
        
        "\n*** C 筹码结构与市场情绪分析 ***",
        "分析{}近1年来机构持股比例变化及筹码结构特点",        
        "对{}进行散户恐慌抛售分析，并进行基于NRBR + 同步性因子 + 多指标交叉验证的量化分析实操推演。",
        "对{}进行机构与散户筹码互换多周期量化分析。将散户恐慌抛售框架（NRBR + 同步性因子）与机构吸筹模型同时扩展至5周、10周、20周窗口，可以系统捕捉从“散户集中恐慌”到“机构完成承接”的全周期筹码互换，有效区分短暂恐慌与趋势性出清。",
        "分析{}空头行为,包括累计沽空占比、近期沽空规模、沽空偏离值、SFC淡仓数据等多个角度.",
        "列举{}的利空利多消息，哪些市场已经反应完了？", 
        "分析{}近期有哪些机构评级调整？",
        "分析{}实际流通股数量及比例，持股机构与个人总数变化趋势，大户特征是否显著。",
        "为什么{}没有吸引到足够多的主动基金？",
        "分析{}能否走出Alpha行情。",
        "分析在未来美股及韩股大幅下跌的情形下，{}是否再继续深度调整。",
        "**分析{}当前所处的牛散和机构的生命周期：筑底、试盘、吸筹、洗盘、主升、派发。",
        "**分析{}行情催化剂",
        
        
        "\n*** D 投资策略 ***",          
        "制定一个基于“猎人模式”的{}投资策略",
        "制定一个基于“农夫模式”的{}投资策略",
        "对{}，综合运用缠论、波浪理论、牛市三段论，结合公司基本面、竞争力优势、盈利质量和潜力等方面特点，以及当前机构观点分歧程度、市场情绪、筹码结构等方面情况，采用政策底、市场底、业绩底、资金底等多维度分析框架，制定一个中长期投资策略，包括建仓、加仓、减仓和清仓等具体操作思路。",    

        "\n*** E 大师视角观点 ***",  
        "从巴菲特的视角，评估{}。",
        "从格雷汉姆的视角，评估{}。",
        "从牛散的视角，评估{}。",

        "\n*** F 分析师视角观点 ***",  
        "从市场技术分析师、基本面分析师的视角，评估{}。",
        "从乐观情景研究员、审慎情景研究员的视角，评估{}。",
        "从高弹性情景分析师、防御情景分析师及基准情景分析师的视角，评估{}。",    
        "从风控治理分析师的视角，评估{}。",
        "从新闻分析师的视角，评估{}。",
        "从社媒分析师的视角，评估{}。",
        "从大盘分析师的视角，评估{}。",
        "从板块分析师的视角，评估{}。",
        "参考以牛散思维框架及多视角分析员讨论会的思维链模板，对{}进行分析和评估，生成整合牛散思维框架、操作要点、提问模板、多视角讨论会、计分权重、会议纪要的深度分析报告。",
        "**采用个股实战超级Prompt V7（决策操作系统版）生成{}的牛散决策参考报告。",
    ]

    # 其他宏观问题
    other_queries = [
        "从价格动量、宏观催化、持仓结构、以及市场间验证四个维度进行交叉判断,对30年期美债收益率见顶的可能性进行量化分析。",
        "分析当前港股VIX指数",
        "分析当前EPFR口径下主动型外资基金多数周度净流出状况。",
        "分析美债收益率走势及其对港股大盘的影响。",
        "从大盘分析师的视角，分析恒升指数走势。",
        "从大盘分析师的视角，分析恒升国企指数走势。",
        "从大盘分析师的视角，分析恒升科技指数走势。",
        "分析港股近期资金流向特点，包括主动资金和被动资金，是净流入还是净流出？哪些板块资金净流入？哪些板块资金净流出?",
        "分析:当前港股是否发生外资撤离？",
        "分析:当前港股是否发生南向资金撤离？",   
        "分析:当前港股有哪些利好利空因素？",      
        "分析:美联储货币政策对港股流动性有哪些影响？",
        "分析:当前M2与社融的数据是否背离",    
        "分析:当前中国股市中融资融券情况",    
        "分析:港股IPO显著增加对港股流动性有哪些影响", 
        "分析:当前港股、A股市场流动性如何？",        
        "分析:当前港股整体估值水平如何？恒升科技股估值水平如何？", 
        "用波浪理论分析恒生科技指数走势", 
        "采用牛市三阶段理论分析恒生科技指数走势",
        "分析:当前财政赤字的规模是否扩张",
        "分析:当前房地产和股市是否同步反弹",
        "分析:当前企业利润和工资是否止跌回升",
    ]

    # 公司比较分析模板（可选添加区间信息）
    comparison_template = "对{}与{}进行多维度比较分析，包括企业战略转型，企业核心竞争力，盈利质量及可持续性，未来3年盈利预测，估值提升，股东回报措施，以及技术分析层面确认股价处于中长期上升通道，或者震荡筑底，或者中长期下降通道，根据2025年财报，计算每股净值（港元）及市净率，ROE及其它等关键财务指标等。"

    # ---------- 数据定义 ----------
    ticker_data = [
        {'ticker': '00371', 'name': '北控水务'},
        {'ticker': '00788', 'name': '中国铁塔'},
        {'ticker': '02202', 'name': '港股万科企业'}, 
        {'ticker': '01951', 'name': '锦鑫生殖'},            
        {'ticker': '00268', 'name': '金蝶国际'},    
        {'ticker': '00354', 'name': '中软国际'},    
        {'ticker': '06060', 'name': '众安在线'},
        {'ticker': '00357', 'name': '美兰空港'},        
        {'ticker': '02602', 'name': '港股万物云'},    
        {'ticker': '01177', 'name': '中生制药'},    
        {'ticker': '01093', 'name': '石药集团'},    
        {'ticker': '03800', 'name': '协鑫科技'},
        {'ticker': '00020', 'name': '商汤科技'},
        {'ticker': '02611', 'name': '国泰海通'},
        {'ticker': '00579', 'name': '京能清洁能源'},
    ]

    # ---------- 定义需要比较的公司对（使用 name 或 ticker 均可） ----------
    comparison_pairs = [
        ('金蝶国际', '中软国际'),   
        ('中生制药', '石药集团'),   
        ('港股万科企业', '港股万物云'),
        ('中生制药', '锦鑫生殖'),      # 也可以用 ticker
        ('众安在线', '国泰海通'),
    ]

    # ---------- 生成各类提问（传入复盘区间参数） ----------
    grouped_queries, used_review_period = generate_queries_grouped_by_company(ticker_data, question_templates, REVIEW_PERIOD)
    comparison_queries = generate_comparison_queries_from_pairs(comparison_pairs, comparison_template, ticker_data, REVIEW_PERIOD)

    # 显示使用的复盘区间
    print(f"\n当前使用的复盘区间: {used_review_period}")
    print(f"（自动计算：本周周一至今日）\n" if REVIEW_PERIOD is None else "")
    
    # ---------- 输出 ----------
    output_filepath = r"C:\Users\Quansheng\Documents\projects\TA_Workflow\Prompt\Prompt_General.txt"
    print_queries(grouped_queries, other_queries, comparison_queries, ticker_data, question_templates, used_review_period)
    save_queries_to_file(output_filepath, grouped_queries, other_queries, comparison_queries, ticker_data, question_templates, used_review_period)
