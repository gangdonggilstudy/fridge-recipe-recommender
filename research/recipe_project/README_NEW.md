크롤러
1. crawl_detail
: 카테고리/목록 페이지에서 레시피 ID를 뽑는 역할.

2. crawl_theme
: 테마 URL 기준으로 여러 페이지를 돌면서 recipe_id를 수집.

3. crawl_detail
: 레시피 상세 페이지에서 제목, 요약, 재료, 조리순서, 태그, 조회수, 스크랩수, 후기수 

4. crawl_review
: 레시피 상세 페이지에서 후기 목록 파싱 


### 레시피 데이터 전체 재수집 실행 순서
1. 레시피 ID 목록 수집
   - crawl_list.py 또는 crawl_theme.py 사용

2. 수집된 recipe_id 중복 제거 후 DB 저장
   - raw_recipes 또는 별도 target 테이블

3. recipe_id 기준 상세정보 수집
   - crawl_detail.py
   - raw_recipes 업데이트

4. recipe_id 기준 리뷰/평점 수집
   - crawl_review.py
   - raw_recipe_review 저장

5. 재료 정규화/분석용 테이블 생성
   - ingredients 파싱
   - raw_ingredients, raw_recipe_ingredient 등 저장

6. 분석 그래프 생성
   - analysis/review_count_distribution.py 실행

   