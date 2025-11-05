README


要件定義

・Googleスプレッドシートで作られたスケジュール表から情報を抽出し、NotionのプロジェクトDBに反映(#sync_sheets_to_notion.py)

・プロジェクトが終わり、Notionにて「進捗」プロパティが「請求済み」となったものに対して「外注費計算」を行う(#outsource_calculation.py)
【外注費計算】
プロジェクトDBから「プロジェクト名」と「外注スタッフ」を。外注DBの「1日単価」プロパティから金額を抽出し、「GTN_外注DB計算シート」と言うGoogleスプレッドシートに反映。

・GTN_外注DB計算シートにて金額の修正が終わったら、GASスクリプトでFlask APIから変数を呼び出し、Notionの「外注費」に反映。（#api.py   #outsource_calculation.py）



格納されているもの

    #わからん
    __pycache__	

    #Google APIキー
    notionsyncproject-e26760681b25.json

    #インストール物
    requirements.txt

    #テスト
    test_notion.py

    #呼び出しFlask
    api.py		
			
    #NotionからGTN外注DB計算シートへ
	outsource_calculation.py

	#スケジュール表からNotionプロジェクトDBへ
	sync_sheets_to_notion.py


使用サービス
        Render
        https://dashboard.render.com/web/srv-cvcbg2rtq21c739t6a00/deploys/dep-cve34l56l47c73aahsp0?r=1h

Render でのデプロイ確認手順
        1. Render ダッシュボードにログインし、対象サービス（google-to-notion）を開く。
        2. 画面上部の Logs タブを選択し、Build ログと Runtime ログを切り替えて依存インストールや起動状況を確認する。
        3. Runtime ログでは検索ボックスを使って `notion.databases.query` などのキーワードを絞り込める。
        4. 不具合が疑われる場合は「Manual Deploy → Clear build cache & deploy」を実行し、依存パッケージを入れ直す。

        アカウント
                ID kei.gtdr@gmail.com
                PSW Kei4ke1991(かな？)


新規PCでの手順

	1.GitHUBで下記アカウントにログイン
		ID kei.gtdr@gmail.com
		PSW Kei4ke1991(かな？)

	2.下記リポジトリをクローン
		GoogleToNotion

	3.








