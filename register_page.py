# register_page.py - 用户注册（管理员用）

import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

st.title("👤 用户注册")

with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

# 注册表单
with st.form("register_form"):
    username = st.text_input("用户名")
    name = st.text_input("显示名称")
    email = st.text_input("邮箱")
    password = st.text_input("密码", type="password")
    password_confirm = st.text_input("确认密码", type="password")
    
    submitted = st.form_submit_button("注册")
    
    if submitted:
        if password != password_confirm:
            st.error("两次密码不一致")
        elif username in config['credentials']['usernames']:
            st.error("用户名已存在")
        else:
            # 生成密码哈希
            hashed_password = stauth.Hasher([password]).generate()[0]
            
            # 添加新用户
            config['credentials']['usernames'][username] = {
                'email': email,
                'name': name,
                'password': hashed_password
            }
            
            # 保存配置
            with open('config.yaml', 'w') as file:
                yaml.dump(config, file, default_flow_style=False)
            
            st.success(f"用户 {username} 注册成功！")
            st.balloons()
