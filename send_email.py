
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

# 网易163邮箱信息
sender_email = '18028320570@163.com'  # 发件人邮箱
smtp_password = 'MMdFS7knZxW4fkun'  # 163邮箱授权码
recipient_email = '18028320570@163.com'  # 收件人邮箱（可以发送给自己）

# 网易163 SMTP服务器设置
smtp_server = 'smtp.163.com'
smtp_port = 465  # 163邮箱SSL端口

# 发送邮件函数
def send_email(subject, body):
    print(f"开始发送邮件，服务器: {smtp_server}:{smtp_port}")
    print(f"发件人: {sender_email}")
    print(f"收件人: {recipient_email}")
    print(f"邮件主题: {subject}")
    
    # 创建邮件对象
    msg = MIMEMultipart()
    msg['From'] = Header(sender_email)
    msg['To'] = Header(recipient_email)
    msg['Subject'] = Header(subject)
    
    # 添加邮件正文
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    print("邮件内容创建成功")
    
    try:
        # 连接SMTP服务器 - 网易163使用SSL连接
        print("正在连接SMTP服务器...")
        server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15)
        server.set_debuglevel(1)  # 启用调试信息
        print("SSL连接成功建立")
        
        # 登录邮箱
        print("正在登录邮箱...")
        server.login(sender_email, smtp_password)
        print("登录成功")
        
        # 发送邮件
        print("正在发送邮件...")
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        print("邮件发送成功!")
        
        # 关闭连接
        server.quit()
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"发送邮件时出错：认证失败 - {str(e)}")
        print("提示：请确认您已启用两步验证并创建了应用专用密码")
        print("或者检查邮箱账户是否允许SMTP访问")
    except smtplib.SMTPConnectError as e:
        print(f"发送邮件时出错：无法连接到SMTP服务器 - {str(e)}")
    except smtplib.SMTPException as e:
        print(f"发送邮件时出错：SMTP错误 - {str(e)}")
    except Exception as e:
        print(f"发送邮件时出错：{str(e)}")
    
    return False

# 主函数：测试邮件发送
if __name__ == "__main__":
    # 邮件主题和内容
    email_subject = "网易163测试邮件"
    email_content = "这是使用Python通过网易163邮箱发送的测试邮件。"
    
    # 发送测试邮件
    print("开始发送测试邮件...")
    success = send_email(email_subject, email_content)
    
    if success:
        print("\n邮件发送任务完成!")
    else:
        print("\n邮件发送失败，请检查以下几点：")
        print("1. 确认授权码是否正确（不是邮箱登录密码）")
        print("2. 确认网易163邮箱已开启POP3/SMTP服务")
        print("3. 检查网络连接是否正常")
        print("4. 查看详细错误信息分析具体原因")