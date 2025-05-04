from app import create_app

app = create_app()

if __name__ == '__main__':
    # 已修复 chunked 编码重复问题
    app.run(debug=True, host='0.0.0.0', port=8876) 