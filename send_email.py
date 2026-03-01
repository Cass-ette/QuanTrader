import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from config import (
    EMAIL_SENDER, EMAIL_SMTP_PASSWORD, EMAIL_RECIPIENT,
    EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT
)


def send_email(subject, body):
    print(f"开始发送邮件，服务器: {EMAIL_SMTP_SERVER}:{EMAIL_SMTP_PORT}")
    print(f"发件人: {EMAIL_SENDER}")
    print(f"收件人: {EMAIL_RECIPIENT}")
    print(f"邮件主题: {subject}")

    msg = MIMEMultipart()
    msg['From'] = Header(EMAIL_SENDER)
    msg['To'] = Header(EMAIL_RECIPIENT)
    msg['Subject'] = Header(subject)

    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    print("邮件内容创建成功")

    try:
        print("正在连接SMTP服务器...")
        server = smtplib.SMTP_SSL(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT, timeout=15)
        server.set_debuglevel(1)
        print("SSL连接成功建立")

        print("正在登录邮箱...")
        server.login(EMAIL_SENDER, EMAIL_SMTP_PASSWORD)
        print("登录成功")

        print("正在发送邮件...")
        text = msg.as_string()
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, text)
        print("邮件发送成功!")

        server.quit()
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"发送邮件时出错：认证失败 - {str(e)}")
        print("提示：请确认您已启用两步验证并创建了应用专用密码")
    except smtplib.SMTPConnectError as e:
        print(f"发送邮件时出错：无法连接到SMTP服务器 - {str(e)}")
    except smtplib.SMTPException as e:
        print(f"发送邮件时出错：SMTP错误 - {str(e)}")
    except Exception as e:
        print(f"发送邮件时出错：{str(e)}")

    return False


if __name__ == "__main__":
    email_subject = "网易163测试邮件"
    email_content = "这是使用Python通过网易163邮箱发送的测试邮件。"

    print("开始发送测试邮件...")
    success = send_email(email_subject, email_content)

    if success:
        print("\n邮件发送任务完成!")
    else:
        print("\n邮件发送失败，请检查以下几点：")
        print("1. 确认授权码是否正确（不是邮箱登录密码）")
        print("2. 确认网易163邮箱已开启POP3/SMTP服务")
        print("3. 检查网络连接是否正常")
        print("4. 检查 .env 中 EMAIL_* 变量是否正确配置")
