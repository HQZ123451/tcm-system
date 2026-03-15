# tcm_web_app.py - 中医智能诊疗系统（带用户登录）

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from neo4j import GraphDatabase
from zhipuai import ZhipuAI
import json
from datetime import datetime

# ========== 页面配置 ==========
st.set_page_config(
    page_title="中医智能诊疗系统",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== 从Secrets读取配置 ==========
NEO4J_URI = st.secrets["NEO4J_URI"]
NEO4J_USER = st.secrets["NEO4J_USER"]
NEO4J_PASSWORD = st.secrets["NEO4J_PASSWORD"]
API_KEY = st.secrets["API_KEY"]

# ========== 初始化连接 ==========
@st.cache_resource
def init_connections():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    client = ZhipuAI(api_key=API_KEY)
    return driver, client

driver, client = init_connections()

# ========== 用户认证 ==========
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

# ========== 登录界面 ==========
name, authentication_status, username = authenticator.login('登录', 'main')

if authentication_status == False:
    st.error('用户名或密码错误')
    st.stop()
elif authentication_status == None:
    st.warning('请输入用户名和密码')
    st.stop()

# ========== 登录成功后的主界面 ==========
authenticator.logout('退出登录', 'sidebar')
st.sidebar.markdown(f'👤 欢迎，**{name}**!')

# ========== 知识库查询类 ==========
class TCMKnowledgeBase:
    def find_diseases_by_symptoms(self, symptom_list):
        query = """
        MATCH (d:疾病)-[:临床表现]->(s:症状)
        WHERE s.name IN $symptoms
        WITH d, count(s) AS 匹配症状数, collect(s.name) AS 匹配的症状
        ORDER BY 匹配症状数 DESC
        RETURN d.name AS 疾病, d.分类 AS 分类, 匹配症状数, 匹配的症状
        LIMIT 5
        """
        with driver.session() as session:
            result = session.run(query, symptoms=symptom_list)
            return [record.data() for record in result]
    
    def find_prescriptions_by_disease(self, disease_name):
        query = """
        MATCH (f:方剂)-[:治疗]->(d:疾病 {name: $disease})
        OPTIONAL MATCH (f)-[:组成]->(m:药物)
        OPTIONAL MATCH (f)-[:属于]->(t:治法)
        RETURN f.name AS 方剂, t.name AS 治法, 
               collect(DISTINCT m.name) AS 药物组成,
               f.组成数量 AS 药味数
        """
        with driver.session() as session:
            result = session.run(query, disease=disease_name)
            return [record.data() for record in result]
    
    def find_pathogenesis(self, disease_name):
        query = """
        MATCH (d:疾病 {name: $disease})
        OPTIONAL MATCH (d)-[:临床表现]->(s:症状)
        OPTIONAL MATCH (d)<-[:治疗]-(f:方剂)
        OPTIONAL MATCH (d)<-[:导致]-(cause)
        OPTIONAL MATCH (d)-[:导致]->(effect)
        RETURN d.name AS 疾病,
               d.分类 AS 分类,
               collect(DISTINCT s.name) AS 症状,
               collect(DISTINCT f.name) AS 治疗方剂,
               collect(DISTINCT cause.name) AS 病因,
               collect(DISTINCT effect.name) AS 可能后果
        """
        with driver.session() as session:
            result = session.run(query, disease=disease_name)
            return result.single().data() if result.peek() else None
    
    def get_all_symptoms(self):
        query = "MATCH (s:症状) RETURN s.name AS name ORDER BY s.name"
        with driver.session() as session:
            result = session.run(query)
            return [record["name"] for record in result]
    
    def get_all_diseases(self):
        query = "MATCH (d:疾病) RETURN d.name AS name ORDER BY d.name"
        with driver.session() as session:
            result = session.run(query)
            return [record["name"] for record in result]

kb = TCMKnowledgeBase()

# ========== AI问答功能 ==========
def ai_answer(question, context=None):
    prompt = f"""你是基于《生命本能系统论》的中医专家。

用户问题：{question}

{background if context else '请根据中医理论回答。'}"""
    
    response = client.chat.completions.create(
        model="glm-4-flash",
        messages=[
            {"role": "system", "content": "你是中医专家，精通《生命本能系统论》"},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

# ========== 页面标题 ==========
st.title("🏥 中医智能诊疗系统")
st.markdown("*基于《生命本能系统论》与Neo4j知识图谱*")
st.divider()

# ========== 侧边栏菜单 ==========
menu = st.sidebar.radio(
    "📋 功能菜单",
    ["🏠 首页", "💬 智能问答", "💊 方剂推荐", "📊 病势分析", "📖 知识查询"]
)

# ========== 【首页】==========
if menu == "🏠 首页":
    st.header("欢迎使用中医智能诊疗系统")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💊 方剂", "60+")
    with col2:
        st.metric("🏥 疾病", "30+")
    with col3:
        st.metric("📋 症状", "40+")
    
    st.info("""
    ### 🎯 系统功能
    
    1. **💬 智能问答** - 有任何中医问题都可以问AI
    2. **💊 方剂推荐** - 输入症状，智能推荐方剂
    3. **📊 病势分析** - 深入了解疾病的病因病势
    4. **📖 知识查询** - 查询方剂、疾病、药物的详细信息
    
    ### 📚 理论基础
    
    本系统基于**郭生白《生命本能系统论》**构建，涵盖：
    - 排异本能系统
    - 自主调节系统
    - 自塑本能系统
    - 自我修复系统
    等十大本能系统的诊疗理论。
    """)
    
    st.divider()
    st.caption(f"当前用户：{name} | 登录时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

# ========== 【智能问答】==========
elif menu == "💬 智能问答":
    st.header("💬 智能问答")
    st.markdown("有任何中医问题，都可以向AI助手提问")
    
    # 显示历史记录（简化版，用session_state）
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # 快捷问题
    quick_questions = [
        "什么是生命本能系统论？",
        "发热的中医原理是什么？",
        "麻黄汤和桂枝汤有什么区别？",
        "高血压在中医里属于什么病势？"
    ]
    
    st.markdown("**💡 快捷问题：**")
    cols = st.columns(4)
    for i, q in enumerate(quick_questions):
        if cols[i].button(q, key=f"q{i}"):
            st.session_state.current_question = q
    
    question = st.text_area("你的问题：", 
                           value=st.session_state.get("current_question", ""),
                           placeholder="例如：发烧怕冷是什么问题？",
                           height=80)
    
    if st.button("🚀 提问", type="primary"):
        if question:
            with st.spinner("🤔 AI思考中..."):
                answer = ai_answer(question)
            
            # 保存历史
            st.session_state.chat_history.append({"q": question, "a": answer})
            
            st.success("回答：")
            st.write(answer)
            
            # 显示相关查询建议
            st.info("💡 **相关查询建议**：可以在'方剂推荐'或'病势分析'中进一步了解")
    
    # 显示历史
    if st.session_state.chat_history:
        with st.expander("📜 历史对话"):
            for item in reversed(st.session_state.chat_history[-5:]):
                st.markdown(f"**问：** {item['q']}")
                st.markdown(f"**答：** {item['a'][:100]}...")
                st.divider()

# ========== 【方剂推荐】==========
elif menu == "💊 方剂推荐":
    st.header("💊 方剂推荐")
    st.markdown("输入症状，系统将根据《生命本能系统论》推荐合适的方剂")
    
    # 获取所有症状
    all_symptoms = kb.get_all_symptoms()
    
    # 症状选择
    st.subheader("📋 选择症状")
    
    # 常用症状快捷选择
    common_symptoms = ["发热", "咳嗽", "头疼", "胸闷", "气短", "心慌", 
                      "腹疼", "便秘", "腹泻", "失眠", "疲劳", "无力"]
    
    st.markdown("**常用症状：**")
    selected_quick = st.multiselect("点击选择", common_symptoms, label_visibility="collapsed")
    
    # 全部症状选择
    selected_all = st.multiselect("或从全部症状中选择", all_symptoms, label_visibility="collapsed")
    
    # 手动输入
    custom_input = st.text_input("手动输入症状（空格分隔）：", 
                                  placeholder="例如：发烧 怕冷 无汗")
    
    # 合并症状
    all_selected = list(set(selected_quick + selected_all))
    if custom_input:
        all_selected.extend(custom_input.replace("，", " ").split())
    
    if st.button("🔍 推荐方剂", type="primary"):
        if not all_selected:
            st.warning("请至少选择一个症状")
        else:
            with st.spinner("🧠 智能分析中..."):
                # 查询可能的疾病
                possible_diseases = kb.find_diseases_by_symptoms(all_selected)
            
            if not possible_diseases:
                st.error("未能找到匹配的疾病，请尝试其他症状组合")
            else:
                st.success(f"**输入症状：**{'、'.join(all_selected)}")
                
                # 显示可能的疾病
                st.subheader("🏥 可能的疾病（按匹配度排序）")
                
                for i, disease in enumerate(possible_diseases[:3], 1):
                    with st.container():
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.metric(f"匹配度 #{i}", f"{disease['匹配症状数']}个症状")
                        with col2:
                            st.markdown(f"### {disease['疾病']}")
                            st.caption(f"分类：{disease['分类']}")
                            st.markdown(f"**匹配症状：**{'、'.join(disease['匹配的症状'])}")
                        
                        # 查询方剂
                        prescriptions = kb.find_prescriptions_by_disease(disease['疾病'])
                        if prescriptions:
                            st.markdown("**💊 推荐方剂：**")
                            for p in prescriptions:
                                with st.expander(f"{p['方剂']}（{p['治法']}）"):
                                    st.markdown(f"**药物组成：**{'、'.join(p['药物组成'])}")
                                    st.markdown(f"**药味数：**{p['药味数']}味")
                        
                        st.divider()

# ========== 【病势分析】==========
elif menu == "📊 病势分析":
    st.header("📊 病势分析")
    st.markdown("深入了解疾病的病因、病势、治疗原则")
    
    all_diseases = kb.get_all_diseases()
    
    # 疾病分类
    disease_categories = {
        "外源性疾病": ["流行性感冒", "肺炎", "麻疹", "脑炎", "非典", "高热"],
        "内源性疾病-代谢类": ["高血压", "糖尿病", "冠心病", "高血脂", "亚健康"],
        "内源性疾病-肿瘤类": ["肿瘤", "脂肪瘤", "肌瘤", "腺体瘤", "息肉", "囊肿", "结肠肿瘤"],
        "内源性疾病-脏腑类": ["肝病", "肾病", "尿毒症"],
        "其他": ["便秘", "黄疸", "水气病", "心脑血管病", "风湿性关节炎", "慢性胃炎", "结肠炎"]
    }
    
    # 选择疾病
    category = st.selectbox("疾病分类", list(disease_categories.keys()))
    disease = st.selectbox("选择疾病", disease_categories[category])
    
    if st.button("📊 分析病势", type="primary"):
        with st.spinner("🔬 深度分析中..."):
            info = kb.find_pathogenesis(disease)
        
        if not info:
            st.error("未找到该疾病的信息")
        else:
            # 显示分析结果
            st.success(f"## {info['疾病']} 病势分析")
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**疾病分类：**{info['分类']}")
            with col2:
                st.info(f"**症状数量：**{len(info['症状'])}个")
            
            # 症状
            with st.expander("📋 临床表现（症状）", expanded=True):
                st.markdown("、".join(info['症状']))
            
            # 治疗方剂
            with st.expander("💊 治疗方剂", expanded=True):
                if info['治疗方剂']:
                    for fang in info['治疗方剂']:
                        st.markdown(f"- {fang}")
                else:
                    st.markdown("暂无方剂信息")
            
            # AI深度分析
            with st.spinner("🤖 AI正在生成深度分析..."):
                prompt = f"""根据《生命本能系统论》分析{disease}：

疾病信息：{json.dumps(info, ensure_ascii=False)}

请详细分析：
1. 这个病属于哪个本能系统的问题？
2. 病势特点和发展规律
3. 治疗原则和思路
4. 日常调理建议
5. 预防和注意事项

用通俗易懂的语言回答。"""

                analysis = client.chat.completions.create(
                    model="glm-4-flash",
                    messages=[
                        {"role": "system", "content": "你是中医专家，精通《生命本能系统论》"},
                        {"role": "user", "content": prompt}
                    ]
                ).choices[0].message.content
            
            with st.expander("💡 AI深度分析", expanded=True):
                st.write(analysis)
            
            # 病因和后果
            if info['病因']:
                st.warning(f"**可能的病因：**{'、'.join(info['病因'])}")
            if info['可能后果']:
                st.error(f"**可能导致的疾病：**{'、'.join(info['可能后果'])}")

# ========== 【知识查询】==========
elif menu == "📖 知识查询":
    st.header("📖 知识查询")
    st.markdown("查询方剂、疾病、药物、治法的详细信息")
    
    query_type = st.selectbox("查询类型", ["方剂查询", "疾病查询", "症状查询", "治法查询"])
    
    if query_type == "方剂查询":
        fangji_name = st.text_input("输入方剂名称：", placeholder="例如：麻黄汤")
        if st.button("查询"):
            # 查询方剂详情
            query = """
            MATCH (f:方剂 {name: $name})
            OPTIONAL MATCH (f)-[:组成]->(m:药物)
            OPTIONAL MATCH (f)-[:属于]->(t:治法)
            OPTIONAL MATCH (f)-[:治疗]->(d:疾病)
            RETURN f.name AS 方剂, f.组成数量 AS 药味数,
                   collect(DISTINCT m.name) AS 组成,
                   collect(DISTINCT t.name) AS 治法,
                   collect(DISTINCT d.name) AS 治疗疾病
            """
            with driver.session() as session:
                result = session.run(query, name=fangji_name)
                data = result.single()
                
                if data:
                    st.success(f"## {data['方剂']}")
                    st.markdown(f"**药味数：**{data['药味数']}味")
                    st.markdown(f"**药物组成：**{'、'.join(data['组成'])}")
                    st.markdown(f"**治法：**{', '.join(data['治法']) or '暂无'}")
                    st.markdown(f"**治疗疾病：**{', '.join(data['治疗疾病']) or '暂无'}")
                else:
                    st.error("未找到该方剂")

# ========== 页脚 ==========
st.divider()
st.caption("🏥 中医智能诊疗系统 | 基于《生命本能系统论》| 毕业设计项目")
