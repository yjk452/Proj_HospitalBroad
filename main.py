from flask import Flask,jsonify, render_template, request, redirect, url_for, session
import pymysql

app = Flask(__name__)
app.secret_key = 'your_secret_key'


# MySQL 연결 설정
def get_db_connection():
    return pymysql.connect(
       host='localhost',
        database='project',
        user='project1',
        password='project1',      # 데이터베이스 이름
        charset='utf8',
        cursorclass=pymysql.cursors.DictCursor)

# 첫 페이지: 증상 리스트 보여주기
@app.route('/')
def home():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        query = "SELECT symptomCD, symptomname FROM symptom"
        cursor.execute(query)
        symptoms = cursor.fetchall()
    conn.close()
    print(symptoms) 
    return render_template('home.html', symptoms=symptoms)

# 증상을 클릭했을 때 해당 증상 관련 병원 조회
@app.route('/symptom/<symptomCD>')
def view_symptom(symptomCD):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # 증상 정보 가져오기
        query_symptom = "SELECT s.symptomCD, s.explain FROM symptom s WHERE symptomCD  = %s"
        cursor.execute(query_symptom, (symptomCD,))
        symptom = cursor.fetchone()

        # 관련 병원 정보 가져오기
        query_hospitals = """
        SELECT h.hospitalname, h.address, h.callnumber, IFNULL(h.link, '정보 없음') AS link, h.field, avg(r.score) as 평균
        FROM hospital h
        JOIN recommend rc ON h.hospitalid = rc.hospitalid
        JOIN symptom s ON rc.symptomCD = s.symptomCD
        join review r on  r.hospitalid = h.hospitalid
        WHERE s.symptomCD = %s
        group by h.hospitalname, h.address, h.callnumber,h.link, h.field;
        """
        cursor.execute(query_hospitals, (symptomCD,))
        hospitals = cursor.fetchall()
    conn.close()
     # 첫 번째와 두 번째 병원만 추출
    hospital1 = hospitals[0] if len(hospitals) > 0 else None
    hospital2 = hospitals[1] if len(hospitals) > 1 else None
    print(hospital1, hospital2) 
    return render_template('symptom.html', symptom=symptom, hospital1=hospital1, hospital2= hospital2, symptom_id=symptomCD)

@app.route('/view_records_and_reviews/<symptomCD>')
def view_records_and_reviews(symptomCD):
    conn = get_db_connection()
     # 진료 내역 가져오기
    with conn.cursor() as cursor:
        query_records = """
        SELECT DISTINCT 
       CASE 
         WHEN SUBSTRING(p.resident_number, 8, 1) IN ('1', '3') THEN '남성'
         WHEN SUBSTRING(p.resident_number, 8, 1) IN ('2', '4') THEN '여성'
         ELSE '알 수 없음'
       END AS 성별,
       LEFT(p.name, 1) AS 성, 
       d.doctorname AS 의사명, 
       h.hospitalname AS 병원명, 
       t.text AS 진료내용,  
       s.explain AS 증상설명,
       s.symptomname AS 증상명
        FROM patient p
        JOIN treatment t ON p.patientID = t.patientID
        JOIN doctor d ON t.doctorID = d.doctorID
        JOIN hospital h ON d.hospitalid = h.hospitalid
        JOIN symptom s ON t.symptomCD = s.symptomCD
        WHERE s.symptomCD = %s
        ORDER BY h.hospitalname, 성; 

        """
        cursor.execute(query_records, (symptomCD,))
        records = cursor.fetchall()
        print(f"{records}")
    
    # 후기 가져오기
    with conn.cursor() as cursor:
        query_reviews = """
        SELECT h.hospitalname as 병원명,m.nickname AS 닉네임, r.score AS 점수, r.content AS 후기내용
        FROM review r
        JOIN member m ON r.memberID = m.memberID
        JOIN hospital h ON r.hospitalid = h.hospitalid
        join recommend rc on rc.hospitalid= h.hospitalid
        WHERE rc.symptomCD = %s
        """
        cursor.execute(query_reviews, (symptomCD,))
        reviews = cursor.fetchall()

    conn.close()
    return render_template('tnr.html', symptomCD=symptomCD, reviews=reviews, records=records)


# 후기 작성
@app.route('/write_review', methods=['GET', 'POST'])
def write_review():
    # 로그인 여부 확인
    if 'memberID' not in session:
        return redirect(url_for('login', next=request.url))  # 로그인 페이지로 리디렉션, 이전 URL 전달

    if request.method == 'POST':
        memberID = session.get('memberID')
        hospitalname = request.form['hospitalname']
        score = request.form['score']
        content = request.form['content']
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 병원 이름으로 병원 ID 조회
            cursor.execute("SELECT hospitalID FROM hospital WHERE hospitalname = %s", (hospitalname,))
            hospital = cursor.fetchone()
            
            if not hospital:
                conn.close()
                return "Hospital not found", 404  # 병원을 찾을 수 없을 때 에러 처리
            
            hospitalID = hospital['hospitalID']  # 병원 ID 가져오기
            
            query = "INSERT INTO review (memberID, hospitalID, score, content) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (memberID, hospitalID, score, content))
            conn.commit()
        conn.close()
        return redirect(url_for('home'))
    return render_template('write_review.html')

# 문의 작성
@app.route('/write_qna', methods=['GET', 'POST'])
def write_qna():
    if request.method == 'POST':
        memberID = session.get('memberID')
        title = request.form['title']
        content = request.form['content']
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = "INSERT INTO question (memberID, title, content) VALUES (%s, %s, %s)"
            cursor.execute(query, (memberID, title, content))
            conn.commit()
        conn.close()
        return redirect(url_for('get_questions'))
    return render_template('write_qna.html')

# 문의 조회
@app.route('/question')
def get_questions():
    # 로그인 여부 확인
    if 'memberID' not in session:  # 세션에 memberID가 없으면 로그인 페이지로 리디렉션
        return redirect(url_for('login', next=request.url))
    
    conn = get_db_connection()
    with conn.cursor() as cursor:
        query = """
        SELECT q.questionCD as 번호, q.title as 제목, m.nickname as 닉네임
        FROM question q, member m 
        WHERE q.memberID = m.memberID
        """
        cursor.execute(query)
        questions = cursor.fetchall()
    conn.close()
    print(questions)
    return render_template('qna.html', questions=questions)

# 문의 상세 조회
@app.route('/question/<int:question_id>')
def view_question(question_id):
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
            SELECT q.title, q.content, q.respond, m.nickname
            FROM question q
            JOIN member m ON q.memberID = m.memberID
            WHERE q.questioncd = %s
            """
            cursor.execute(query, (question_id,))
            question = cursor.fetchone()
        conn.close()
        return render_template('view_qna.html', question=question)
# 로그인
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        memberID = request.form['memberID']
        memberPW = request.form['memberPW']

        if not memberID or not memberPW:
            return jsonify({'status': 'error', 'message': "아이디와 비밀번호를 입력해주세요."})

        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 관리자 확인
            admin_query = "SELECT * FROM administrator WHERE adminID = %s AND adminPW = %s"
            cursor.execute(admin_query, (memberID, memberPW))
            admin = cursor.fetchone()

            # 사용자 확인
            user_query = "SELECT * FROM member WHERE memberID = %s AND memberPW = %s"
            cursor.execute(user_query, (memberID, memberPW))
            user = cursor.fetchone()

        conn.close()

        # 로그인 성공 처리
        if admin:
            session['adminID'] = admin['adminID']
            return jsonify({'status': 'success', 'type': 'admin', 'redirect_url': url_for('admin_home')})
        elif user:
            session['memberID'] = user['memberID']
            next_page = request.args.get('next') or url_for('home')
            return jsonify({'status': 'success', 'type': 'user', 'redirect_url': next_page})
        else:
            # 로그인 실패
            return jsonify({'status': 'error', 'message': "아이디 또는 비밀번호가 올바르지 않습니다."})

    return render_template('login.html', next=request.args.get('next', '/'))
# 로그아웃
@app.route('/logout')
def logout():
    session.pop('memberID', None)
    session.pop('adminID', None)
    return redirect(url_for('home'))
# 회원가입
@app.route('/join', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        memberID = request.form['memberID']
        memberPW = request.form['memberPW']
        nickname = request.form['nickname']
        phone = request.form['phone']
        gender = request.form['gender']
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = "INSERT INTO member (memberID, memberPW, nickname, phone, gender) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(query, (memberID, memberPW, nickname, phone, gender))
            conn.commit()
        conn.close()
        return jsonify(url_for('login'))
    return render_template('join.html')

# 관리자 홈
@app.route('/admin_home')
def admin_home():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        query = """
        SELECT q.questionCD as 번호, q.title as 제목, m.nickname as 닉네임
        FROM question q, member m 
        WHERE q.memberID = m.memberID
        """
        cursor.execute(query)
        questions = cursor.fetchall()
    conn.close()
    print(questions)
    return render_template('view_admin_qna.html', questions=questions)

#관리자 문의사항 답변
@app.route('/answer_question/<int:question_id>', methods=['GET', 'POST'])
def answer_question(question_id):
    if request.method == 'POST':
        answer = request.form['answer']
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = "UPDATE question SET respond = %s WHERE questioncd = %s"
            cursor.execute(query, (answer, question_id))
            conn.commit()
        conn.close()
        return redirect(url_for('admin_home'))
       
    conn = get_db_connection()
    with conn.cursor() as cursor:
        query = "SELECT title, content, respond FROM question WHERE questioncd = %s"
        cursor.execute(query, (question_id,))
        question = cursor.fetchone()
    conn.close()
    return render_template('answer_question.html', question_id= question_id, question=question)

#관리자 문의 삭제
@app.route('/delete_question/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        query = "DELETE FROM question WHERE questioncd = %s"
        cursor.execute(query, (question_id,))
        conn.commit()
    conn.close()
    return '', 204  # 아무런 내용을 반환하지 않고 HTTP 204 (No Content) 상태로 응답

if __name__ == '__main__':
    app.run(debug=True)
