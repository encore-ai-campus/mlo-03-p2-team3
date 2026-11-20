# Silver 컬럼 사전

[작업 기록](SILVER.md) · [변경 건수](SILVER_CHANGES.md) · [사용법](silver_usage.md)

실제 생성한 Parquet 스키마와 집계입니다. 타임스탬프는 Asia/Seoul(KST), 금액은 원, 거리 m, 무게 kg, 시간 길이는 초입니다.

## BET_ORDER

저장 파일명: `BET_ORDER.parquet`, **27,907행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ORDER_NO` | `string` | order_no | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `BC00489449; BC00489459; BC00489476` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `ORDER_TYPE_CD` | `string` | order_type_cd | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `CANCEL; CANCEL; CANCEL` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `ORIG_ORDER_NO` | `string` | orig_order_no | TRIM·빈값 처리 후 지정 타입 변환 | 24,446 | {"EMPTY": 24446} | `NULL; NULL; NULL` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `MBR_NO` | `string` | member_no | TRIM·대문자·코드 확인 | 4,921 | {"EMPTY": 4921} | `M0016321; M0017592; M0013293` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `CHNL_CD` | `string` | channel_cd | OTB 지점 분리·채널 코드화·빈값 UNKNOWN | 0 | {} | `OTB; ONSITE; ONSITE` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `OTB_BRANCH_NO` | `string` | channel_cd | OTB 지점번호 분리·앞자리 0 보존 | 26,364 | {"NOT_OTB": 26364} | `01; NULL; NULL` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `SALE_DTM` | `timestamp[ms, tz=Asia/Seoul]` | sale_dtm | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-29 10:33:00; 2026-05-22 10:44:00; 2026-05-22 10:55:00` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `BIZ_DT` | `date32[day]` | biz_date | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-29; 2026-05-22; 2026-05-22` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TICKET_CNT` | `int32` | ticket_cnt | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `9; 13; 1` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TOTAL_AMT` | `int64` | total_amt | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `-61000; -44600; -3600` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `SOURCE_FILE` | `string` | source_file | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `bet_order.csv; bet_order.csv; bet_order.csv` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-11-20 14:40:35; 2026-11-20 14:40:35; 2026-11-20 14:40:35` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `order/bet_order.parquet; order/bet_order.parquet; order/bet_order.parquet` | TRACE-01 |

## BET_TICKET

저장 파일명: `BET_TICKET.parquet`, **523,416행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ORDER_NO` | `string` | order_no | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `BC00489449; BC00489449; BC00489449` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TICKET_SEQ` | `int32` | ticket_seq | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `1; 2; 3` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `RC_DT` | `date32[day]` | rc_date | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-29; 2026-05-29; 2026-05-29` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `RC_NO` | `int32` | rc_no | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `9; 9; 9` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `BET_TYPE_CD` | `string` | bet_type_cd | 원천값을 명시된 표준 코드로 매핑 | 0 | {} | `QNL; WIN; WIN` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `CHUL_NO` | `int32` | chul_no | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `1; 1; 1` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `HR_NM` | `string` | hr_name | TRIM·빈값 처리 후 지정 타입 변환 | 1,563 | {"EMPTY": 1563} | `일사만리; 일사만리; 일사만리` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `CHUL_NO2` | `int32` | chul_no2 | TRIM·빈값 처리 후 지정 타입 변환 | 416,107 | {"EMPTY": 416107} | `8; NULL; NULL` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `HR_NM2` | `string` | hr_name2 | TRIM·빈값 처리 후 지정 타입 변환 | 416,107 | {"EMPTY": 416107} | `한백제왕; NULL; NULL` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `UNIT_CNT` | `int32` | ticket_cnt | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `-108; -30; -52` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `BET_AMT` | `int32` | bet_amt | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `-10800; -3000; -5200` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TICKET_STAT_CD` | `string` | ticket_status | TRIM·대문자·코드 확인 | 0 | {} | `CANCEL; CANCEL; CANCEL` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `SOURCE_FILE` | `string` | source_file | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `bet_ticket.csv; bet_ticket.csv; bet_ticket.csv` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-11-20 14:40:35; 2026-11-20 14:40:35; 2026-11-20 14:40:35` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `order/bet_ticket.parquet; order/bet_ticket.parquet; order/bet_ticket.parquet` | TRACE-01 |

## MBR_MASTER

저장 파일명: `MBR_MASTER.parquet`, **4,383행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MBR_NO` | `string` | MBR_NO | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `M0012346; M0012347; M0012348` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `BIRTH_DT` | `date32[day]` | BIRTH_DT | TRIM·빈값 처리 후 지정 타입 변환 | 27 | {"EMPTY": 27} | `1957-10-25; 1957-12-06; 1953-11-07` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `JOIN_DT` | `date32[day]` | JOIN_DT | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2022-03-23; 2023-07-17; 2022-08-13` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `REGION_CD` | `string` | REGION_NM | 지역명을 공용 약칭으로 매핑 | 0 | {} | `경북; 경기; 인천` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `MBR_GRADE_CD` | `string` | MBR_GRADE_CD | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `NORMAL; NORMAL; NORMAL` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `MBR_STAT_CD` | `string` | MBR_STAT_CD | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `10; 10; 10` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `SOURCE_FILE` | `string` | source_file | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `MBR_MASTER.csv; MBR_MASTER.csv; MBR_MASTER.csv` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-11-20 14:40:35; 2026-11-20 14:40:35; 2026-11-20 14:40:35` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `member/MBR_MASTER.parquet; member/MBR_MASTER.parquet; member/MBR_MASTER.parquet` | TRACE-01 |

## HR_WEEKLY_SNAPSHOT

저장 파일명: `HR_WEEKLY_SNAPSHOT.parquet`, **52,642행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `SNAPSHOT_DT` | `date32[day]` | SNAPSHOT_DT | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-20; 2026-05-20; 2026-05-20` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `HR_NM` | `string` | HR_NAME | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `가라공주; 가문의여신; 가속의힘` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `HR_SEX_CD` | `string` | SEX_NM | 원천값을 명시된 표준 코드로 매핑 | 0 | {} | `F; F; F` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `HR_BIRTH_DT` | `date32[day]` | BIRTH_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2022-05-15; 2023-03-24; 2023-04-24` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `HR_AGE` | `int32` | AGE_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `4; 3; 3` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `HR_GRADE_CD` | `string` | GRADE_RAW | 말 등급을 표준 코드로 매핑 | 0 | {} | `6; 6; NONE` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `TR_GRP_NO` | `string` | TR_GRP_NO | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `88; 88; 08` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TR_NM` | `string` | TR_NAME | 외부마 표시를 NULL로 분리 | 25,428 | {"EXTERNAL_HORSE": 25428} | `NULL; NULL; 문성호` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `TR_EXTERNAL_YN` | `string` | TR_NAME | 외부마 여부 Y/N 생성 | 0 | {} | `Y; Y; N` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `OW_NM` | `string` | OW_NAME | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `조종호; 김영구; 고영조` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TOT_RC_CNT` | `int32` | TOT_RC_CNT | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `5; 2; 0` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TOT_1ST_CNT` | `int32` | TOT_1ST | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `0; 0; 0` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TOT_2ND_CNT` | `int32` | TOT_2ND | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `1; 0; 0` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TOT_3RD_CNT` | `int32` | TOT_3RD | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `0; 0; 0` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `Y1_RC_CNT` | `int32` | Y1_RC_CNT | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `5; 2; 0` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `Y1_1ST_CNT` | `int32` | Y1_1ST | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `0; 0; 0` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `Y1_2ND_CNT` | `int32` | Y1_2ND | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `1; 0; 0` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `Y1_3RD_CNT` | `int32` | Y1_3RD | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `0; 0; 0` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `PRIZE_AMT` | `int64` | PRIZE_AMT_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `3220000; 700000; 0` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `RATING_VAL` | `int32` | RATING_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 18,298 | {"EMPTY": 18298} | `NULL; NULL; NULL` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INTRO_AMT` | `int64` | INTRO_PRICE_RAW | 도입 가격 분리·천원→원 | 12,363 | {"SELF_BRED": 12363} | `3000000; 15000000; NULL` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `INTRO_TYPE_NM` | `string` | INTRO_PRICE_RAW | 도입 유형 분리 | 0 | {} | `개별; 개별; 자가생산` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `SIRE_NM` | `string` | SIRE_NAME | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `화룡특급; 오라태양; 일대태수` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `DAM_NM` | `string` | DAM_NAME | TRIM·빈값 처리 후 지정 타입 변환 | 397 | {"EMPTY": 397} | `희망여신; 가문의전설; 세계의보물` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `SOURCE_FILE` | `string` | source_file | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `HR_WEEKLY_SNAPSHOT.csv; HR_WEEKLY_SNAPSHOT.csv; HR_WEEKLY_SNAPSHOT.csv` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-11-20 14:40:35; 2026-11-20 14:40:35; 2026-11-20 14:40:35` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `horse/HR_WEEKLY_SNAPSHOT.parquet; horse/HR_WEEKLY_SNAPSHOT.parquet; horse/HR_WEEKLY_SNAPSHOT.parquet` | TRACE-01 |

## TR_WEEKLY_SNAPSHOT

저장 파일명: `TR_WEEKLY_SNAPSHOT.parquet`, **954행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `SNAPSHOT_DT` | `date32[day]` | SNAPSHOT_DT | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-20; 2026-05-20; 2026-05-20` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TR_NM` | `string` | TR_NAME | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `강대은; 강영진; 강태종` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TR_GRP_NO` | `string` | GRP_NO | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `03; 15; 09` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TR_BIRTH_DT` | `date32[day]` | BIRTH_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `1964-01-04; 1970-10-04; 1964-04-06` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TR_AGE` | `int32` | AGE_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `62; 55; 62` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TR_DEBUT_DT` | `date32[day]` | DEBUT_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2002-04-29; 2009-09-09; 2019-03-24` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TOT_RC_CNT` | `int32` | TOT_RC_CNT | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `8211; 6783; 2288` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TOT_1ST_CNT` | `int32` | TOT_1ST | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `828; 837; 280` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TOT_2ND_CNT` | `int32` | TOT_2ND | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `826; 819; 260` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TOT_3RD_CNT` | `int32` | TOT_3RD | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `843; 696; 246` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `Y1_RC_CNT` | `int32` | Y1_RC_CNT | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `293; 477; 360` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `Y1_1ST_CNT` | `int32` | Y1_1ST | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `23; 61; 38` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `Y1_2ND_CNT` | `int32` | Y1_2ND | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `29; 55; 49` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `Y1_3RD_CNT` | `int32` | Y1_3RD | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `17; 46; 47` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `SOURCE_FILE` | `string` | source_file | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `TR_WEEKLY_SNAPSHOT.csv; TR_WEEKLY_SNAPSHOT.csv; TR_WEEKLY_SNAPSHOT.csv` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-11-20 14:40:35; 2026-11-20 14:40:35; 2026-11-20 14:40:35` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `horse/TR_WEEKLY_SNAPSHOT.parquet; horse/TR_WEEKLY_SNAPSHOT.parquet; horse/TR_WEEKLY_SNAPSHOT.parquet` | TRACE-01 |

## RC_RACE

저장 파일명: `RC_RACE.parquet`, **386행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `RC_DT` | `date32[day]` | RC_DATE | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-22; 2026-05-22; 2026-05-22` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `RC_NO` | `int32` | RC_NO | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `1; 2; 3` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `MEET_CD` | `string` | MEET_NM | 원천값을 명시된 표준 코드로 매핑 | 0 | {} | `JEJU; JEJU; JEJU` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `RC_DAY_SEQ` | `int32` | RC_DAY_RAW | 규정된 단위 표현에서 정수 추출 | 0 | {} | `40; 40; 40` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `RC_DIST_M` | `int32` | RC_DIST_RAW | 규정된 단위 표현에서 정수 추출 | 0 | {} | `900; 1000; 900` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `RC_GRADE_CD` | `string` | RANK_RAW | 경주 등급 분리 | 0 | {} | `6; 6; 5` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `BUDAM_TYPE_CD` | `string` | RANK_RAW | 부담 방식 분리 | 6 | {"NO_BURDEN_TYPE": 6} | `SPECIAL_A; SPECIAL_A; HANDICAP` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `HR_CLASS_NM` | `string` | RC_COND_RAW | 경주 조건에서 마종 분리 | 0 | {} | `제주마; 제주마; 제주마` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `RC_TITLE_NM` | `string` | RC_COND_RAW | 경주명 분리·일반 경주는 NULL | 361 | {"GENERAL_RACE": 361} | `NULL; NULL; NULL` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `WEATHER_CD` | `string` | WEATHER_TRACK_RAW | 날씨 원문을 코드로 분리 | 0 | {} | `CLOUDY; CLOUDY; CLOUDY` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `TRACK_STAT_CD` | `string` | WEATHER_TRACK_RAW | 주로 상태 원문을 코드로 분리 | 0 | {} | `MOIST; MOIST; MOIST` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `TRACK_MOIST_RT` | `decimal128(5, 1)` | WEATHER_TRACK_RAW | 함수율 분리·표시 없으면 NULL | 21 | {"NO_MOISTURE": 21} | `14.0; 14.0; 14.0` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `PRIZE1_AMT` | `int64` | PRIZE_RAW | 순위상금 분리·만원→원 | 0 | {} | `7000000; 7000000; 10500000` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `PRIZE2_AMT` | `int64` | PRIZE_RAW | 순위상금 분리·만원→원 | 0 | {} | `3220000; 3220000; 4830000` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `PRIZE3_AMT` | `int64` | PRIZE_RAW | 순위상금 분리·만원→원 | 0 | {} | `2100000; 2100000; 3150000` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `PRIZE4_AMT` | `int64` | PRIZE_RAW | 순위상금 분리·만원→원 | 0 | {} | `980000; 980000; 1470000` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `PRIZE5_AMT` | `int64` | PRIZE_RAW | 순위상금 분리·만원→원 | 0 | {} | `700000; 700000; 1050000` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `START_TM` | `time32[ms]` | START_TM_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `10:45:00; 11:10:00; 12:15:00` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `START_DTM` | `timestamp[ms, tz=Asia/Seoul]` | RC_DATE + START_TM_RAW | 경주일과 출발 시각을 KST 일시로 결합 | 0 | {} | `2026-05-22 10:45:00; 2026-05-22 11:10:00; 2026-05-22 12:15:00` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `SOURCE_FILE` | `string` | source_file | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `RC_RACE.csv; RC_RACE.csv; RC_RACE.csv` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-11-20 14:40:37; 2026-11-20 14:40:37; 2026-11-20 14:40:37` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `race/RC_RACE.parquet; race/RC_RACE.parquet; race/RC_RACE.parquet` | TRACE-01 |

## RC_ENTRY

저장 파일명: `RC_ENTRY.parquet`, **3,666행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `RC_DT` | `date32[day]` | RC_DATE | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-22; 2026-05-22; 2026-05-22` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `RC_NO` | `int32` | RC_NO | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `1; 1; 1` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `CHUL_NO` | `int32` | CHUL_NO | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `6; 10; 8` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `HR_NM` | `string` | HR_NAME | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `센돌이; 전설마루; 달의울림` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `HR_SEX_CD` | `string` | HR_SEX | 원천값을 명시된 표준 코드로 매핑 | 0 | {} | `G; G; F` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `HR_AGE` | `int32` | HR_AGE | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `3; 3; 3` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `BUDAM_KG` | `decimal128(4, 1)` | WG_BUDAM_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `55.0; 55.0; 55.0` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `JK_NM` | `string` | JK_NAME | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `박성광; 이성민; 전현준` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TR_NM` | `string` | TR_NAME | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `이태용; 고영덕; 최기호` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `OW_NM` | `string` | OW_NAME | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `오치영; 김창균; 문귀임` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `RATING_VAL` | `int32` | RATING_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 716 | {"EMPTY": 716} | `NULL; NULL; NULL` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `SOURCE_FILE` | `string` | source_file | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `RC_ENTRY.csv; RC_ENTRY.csv; RC_ENTRY.csv` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-11-20 14:40:37; 2026-11-20 14:40:37; 2026-11-20 14:40:37` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `race/RC_ENTRY.parquet; race/RC_ENTRY.parquet; race/RC_ENTRY.parquet` | TRACE-01 |

## RC_ODDS

저장 파일명: `RC_ODDS.parquet`, **3,666행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `RC_DT` | `date32[day]` | RC_DATE | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-22; 2026-05-22; 2026-05-22` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `RC_NO` | `int32` | RC_NO | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `1; 1; 1` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `CHUL_NO` | `int32` | CHUL_NO | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `6; 10; 8` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `SECT1_SEC` | `decimal128(5, 1)` | SECTION_TIMES_RAW | 7글자 고정폭 위치별 구간→초 | 22 | {"EMPTY": 22} | `48.8; 48.1; 49.2` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `SECT2_SEC` | `decimal128(5, 1)` | SECTION_TIMES_RAW | 7글자 고정폭 위치별 구간→초 | 22 | {"EMPTY": 22} | `16.7; 17.4; 17.0` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `SECT3_SEC` | `decimal128(5, 1)` | SECTION_TIMES_RAW | 7글자 고정폭 위치별 구간→초 | 3,640 | {"EMPTY": 22, "NO_SECTION": 3618} | `NULL; NULL; NULL` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `SECT4_SEC` | `decimal128(5, 1)` | SECTION_TIMES_RAW | 7글자 고정폭 위치별 구간→초 | 3,399 | {"EMPTY": 22, "NO_SECTION": 3377} | `NULL; NULL; NULL` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `SECT5_SEC` | `decimal128(5, 1)` | SECTION_TIMES_RAW | 7글자 고정폭 위치별 구간→초 | 22 | {"EMPTY": 22} | `24.4; 25.2; 24.8` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `SECT6_SEC` | `decimal128(5, 1)` | SECTION_TIMES_RAW | 7글자 고정폭 위치별 구간→초 | 22 | {"EMPTY": 22} | `40.4; 41.4; 41.0` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `SECT7_SEC` | `decimal128(5, 1)` | SECTION_TIMES_RAW | 7글자 고정폭 위치별 구간→초 | 22 | {"EMPTY": 22} | `16.8; 15.8; 17.1` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `WIN_ODDS` | `decimal128(6, 1)` | WIN_ODDS_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 22 | {"MARKER_NULL": 22} | `1.9; 4.6; 12.2` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `PLC_ODDS` | `decimal128(6, 1)` | PLACE_ODDS_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 22 | {"MARKER_NULL": 22} | `1.1; 1.4; 2.3` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `SOURCE_FILE` | `string` | source_file | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `RC_ODDS.csv; RC_ODDS.csv; RC_ODDS.csv` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-11-20 14:40:37; 2026-11-20 14:40:37; 2026-11-20 14:40:37` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `race/RC_ODDS.parquet; race/RC_ODDS.parquet; race/RC_ODDS.parquet` | TRACE-01 |

## RC_RESULT

저장 파일명: `RC_RESULT.parquet`, **3,666행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `RC_DT` | `date32[day]` | RC_DATE | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-22; 2026-05-22; 2026-05-22` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `RC_NO` | `int32` | RC_NO | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `1; 1; 1` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `FINISH_ORD` | `int32` | ORD_RAW | 착순 분리·94/95는 NULL | 22 | {"NOT_RAN": 22} | `1; 2; 3` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `ENTRY_STAT_CD` | `string` | ORD_RAW | 출전 상태 코드 분리 | 0 | {} | `RAN; RAN; RAN` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `CHUL_NO` | `int32` | CHUL_NO | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `6; 10; 8` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `HR_NM` | `string` | HR_NAME | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `센돌이; 전설마루; 달의울림` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `HR_WGT_KG` | `int32` | WG_HR_RAW | 마체중 분리·미출전 0은 NULL | 22 | {"NOT_RAN_WEIGHT": 22} | `279; 285; 260` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `HR_WGT_DIFF_KG` | `int32` | WG_HR_RAW | 체중 증감 분리·첫 측정/미출전 NULL | 389 | {"FIRST_MEASUREMENT": 367, "NOT_RAN_WEIGHT": 22} | `14; -3; 1` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `RC_TIME_SEC` | `decimal128(5, 1)` | RC_TIME_RAW | 분:초를 초로 환산·미출전 표현 NULL | 22 | {"NOT_RAN": 22} | `73.2; 73.3; 74.0` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `MARGIN_LEN` | `decimal128(5, 2)` | MARGIN_RAW | 숫자·분수 착차를 소수로 변환 | 969 | {"EMPTY": 386, "NON_NUMERIC_MARGIN": 583} | `NULL; NULL; 4.00` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `MARGIN_CD` | `string` | MARGIN_RAW | 착차 유형 코드화·빈값 FIRST | 0 | {} | `FIRST; NECK; LEN` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `PASS_ORD_S1` | `int32` | PASS_ORD_RAW + ORD_RAW | 통과 순위 6개 위치 분리·기록 없는 위치 NULL | 22 | {"D-NORM-001_NO_RUN_RECORD": 22} | `1; 6; 3` | MAP-07;D-NORM-001 |
| `PASS_ORD_S2` | `int32` | PASS_ORD_RAW + ORD_RAW | 통과 순위 6개 위치 분리·기록 없는 위치 NULL | 3,640 | {"D-NORM-001_NO_RUN_RECORD": 22, "NO_PASS_POSITION": 3618} | `NULL; NULL; NULL` | MAP-07;D-NORM-001 |
| `PASS_ORD_S3` | `int32` | PASS_ORD_RAW + ORD_RAW | 통과 순위 6개 위치 분리·기록 없는 위치 NULL | 3,471 | {"D-NORM-001_NO_RUN_RECORD": 22, "NO_PASS_POSITION": 3449} | `NULL; NULL; NULL` | MAP-07;D-NORM-001 |
| `PASS_ORD_S4` | `int32` | PASS_ORD_RAW + ORD_RAW | 통과 순위 6개 위치 분리·기록 없는 위치 NULL | 22 | {"D-NORM-001_NO_RUN_RECORD": 22} | `1; 6; 4` | MAP-07;D-NORM-001 |
| `PASS_ORD_S5` | `int32` | PASS_ORD_RAW + ORD_RAW | 통과 순위 6개 위치 분리·기록 없는 위치 NULL | 22 | {"D-NORM-001_NO_RUN_RECORD": 22} | `1; 6; 4` | MAP-07;D-NORM-001 |
| `PASS_ORD_S6` | `int32` | PASS_ORD_RAW + ORD_RAW | 통과 순위 6개 위치 분리·기록 없는 위치 NULL | 22 | {"D-NORM-001_NO_RUN_RECORD": 22} | `1; 6; 2` | MAP-07;D-NORM-001 |
| `SOURCE_FILE` | `string` | source_file | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `RC_RESULT.csv; RC_RESULT.csv; RC_RESULT.csv` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-11-20 14:40:37; 2026-11-20 14:40:37; 2026-11-20 14:40:37` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `race/RC_RESULT.parquet; race/RC_RESULT.parquet; race/RC_RESULT.parquet` | TRACE-01 |

## RC_SALES

저장 파일명: `RC_SALES.parquet`, **2,702행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `RC_DT` | `date32[day]` | RC_DATE | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-22; 2026-05-22; 2026-05-22` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `RC_NO` | `int32` | RC_NO | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `1; 1; 1` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `BET_TYPE_CD` | `string` | POOL_NM | 원천값을 명시된 표준 코드로 매핑 | 0 | {} | `WIN; PLC; QNL` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `SALES_AMT` | `int64` | SALES_AMT_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `12548000; 24207200; 289459600` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `SOURCE_FILE` | `string` | source_file | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `RC_SALES.csv; RC_SALES.csv; RC_SALES.csv` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-11-20 14:40:37; 2026-11-20 14:40:37; 2026-11-20 14:40:37` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `race/RC_SALES.parquet; race/RC_SALES.parquet; race/RC_SALES.parquet` | TRACE-01 |

## RC_SALES_TOTAL

저장 파일명: `RC_SALES_TOTAL.parquet`, **386행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `RC_DT` | `date32[day]` | RC_DATE | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-22; 2026-05-22; 2026-05-22` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `RC_NO` | `int32` | RC_NO | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `1; 2; 3` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `SALES_AMT` | `int64` | SALES_AMT_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `1198915900; 1318174100; 1604422300` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `SOURCE_FILE` | `string` | source_file | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `RC_SALES.csv; RC_SALES.csv; RC_SALES.csv` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-11-20 14:40:37; 2026-11-20 14:40:37; 2026-11-20 14:40:37` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `8; 16; 24` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `race/RC_SALES.parquet; race/RC_SALES.parquet; race/RC_SALES.parquet` | TRACE-01 |

## HR_VET_HIST

저장 파일명: `HR_VET_HIST.parquet`, **1,488행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `VET_DT` | `date32[day]` | VET_DT_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-16; 2026-05-16; 2026-05-16` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `HR_NM` | `string` | HR_NAME | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `대방가; 사라호; 색달미소` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TR_GRP_NO` | `string` | TR_GRP_NO | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `05; 19; 06` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `VET_PLACE_NM` | `string` | VET_PLACE_NM | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `KRA 제주경마; KRA 제주경마; KRA 제주경마` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `VET_NM` | `string` | VET_NM_RAW | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `우전지파행; 좌전지파행; 기타 파행` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `REPORT_DT` | `date32[day]` | REPORT_DT | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-20; 2026-05-20; 2026-05-20` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `SOURCE_FILE` | `string` | source_file | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `HR_VET_HIST.csv; HR_VET_HIST.csv; HR_VET_HIST.csv` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-11-20 14:40:35; 2026-11-20 14:40:35; 2026-11-20 14:40:35` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `VET_SEQ` | `int32` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `horse/HR_VET_HIST.parquet; horse/HR_VET_HIST.parquet; horse/HR_VET_HIST.parquet` | TRACE-01 |

## HR_VET_TYPE_BRIDGE

저장 파일명: `HR_VET_TYPE_BRIDGE.parquet`, **1,664행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `VET_TYPE_NM` | `string` | VET_NM_RAW | 원천 진료명을 쉼표로 분리·항목 공백 제거 | 0 | {} | `우전지파행; 좌전지파행; 기타 파행` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `VET_SEQ` | `int32` | VET_NM_RAW | 부모 진료 이력의 VET_SEQ 연결 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `VET_TYPE_SEQ` | `int32` | VET_NM_RAW | 진료명 항목의 1부터 시작하는 순번 | 0 | {} | `1; 1; 1` | TRACE-01 |
| `SOURCE_FILE` | `string` | source_file | 부모 진료 이력의 출처 상속 | 0 | {} | `HR_VET_HIST.csv; HR_VET_HIST.csv; HR_VET_HIST.csv` | TRACE-01 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | 부모 진료 이력의 출처 상속 | 0 | {} | `2026-11-20 14:40:35; 2026-11-20 14:40:35; 2026-11-20 14:40:35` | TRACE-01 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `horse/HR_VET_HIST.parquet; horse/HR_VET_HIST.parquet; horse/HR_VET_HIST.parquet` | TRACE-01 |

## RC_CHANGE_EVENT

저장 파일명: `RC_CHANGE_EVENT.parquet`, **149행**.

| 표준컬럼 | 실제 타입 | 원천컬럼/생성 근거 | 처리 | NULL 수 | NULL 이유별 건수 | 처음 3행 예시 | 규칙 ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `EVENT_TYPE_CD` | `string` | eventType | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `TRACK_STATUS; TRACK_STATUS; JOCKEY_CHANGE` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `ANNOUNCE_DTM` | `timestamp[ms, tz=Asia/Seoul]` | announcedAt | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-05-22 23:58:00; 2026-05-23 23:58:00; 2026-05-23 23:58:00` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `RC_DT` | `date32[day]` | race.rcDate | TRIM·빈값 처리 후 지정 타입 변환 | 52 | {"SOURCE_NULL": 52} | `NULL; NULL; 2026-05-23` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `RC_NO` | `int32` | race.rcNo | TRIM·빈값 처리 후 지정 타입 변환 | 52 | {"SOURCE_NULL": 52} | `NULL; NULL; 1` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `CHUL_NO` | `int32` | horse.chulNo | TRIM·빈값 처리 후 지정 타입 변환 | 52 | {"SOURCE_NULL": 52} | `NULL; NULL; 6` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `HR_NM` | `string` | horse.hrName | TRIM·빈값 처리 후 지정 타입 변환 | 52 | {"SOURCE_NULL": 52} | `NULL; NULL; 원평가속도` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `BEF_JK_NM` | `string` | change.before | TRIM·빈값 처리 후 지정 타입 변환 | 74 | {"SOURCE_NULL": 74} | `NULL; NULL; 나유나` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `AFT_JK_NM` | `string` | change.after | TRIM·빈값 처리 후 지정 타입 변환 | 74 | {"SOURCE_NULL": 74} | `NULL; NULL; 임재광` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `BUDAM_KG` | `decimal128(4, 1)` | change.budamRaw | TRIM·빈값 처리 후 지정 타입 변환 | 74 | {"SOURCE_NULL": 74} | `NULL; NULL; 55.0` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `CHG_REASON_NM` | `string` | change.reason | TRIM·빈값 처리 후 지정 타입 변환 | 74 | {"SOURCE_NULL": 74} | `NULL; NULL; 감기몸살` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `SCRATCH_REASON_NM` | `string` | reason | TRIM·빈값 처리 후 지정 타입 변환 | 127 | {"SOURCE_NULL": 127} | `NULL; NULL; NULL` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `TRACK_STAT_CD` | `string` | trackRaw | 이벤트 주로 상태 코드화 | 97 | {"SOURCE_NULL": 97} | `MOIST; MOIST; NULL` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `TRACK_MOIST_RT` | `decimal128(5, 1)` | trackRaw | 이벤트 함수율 분리 | 97 | {"SOURCE_NULL": 97} | `14.0; 12.0; NULL` | MAP-01;MAP-04;MAP-06;MAP-07;MAP-10 |
| `SOURCE_FILE` | `string` | source_file | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `race_change_events.jsonl; race_change_events.jsonl; race_change_events.jsonl` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `INGESTED_AT` | `timestamp[ms, tz=Asia/Seoul]` | ingested_at | TRIM·빈값 처리 후 지정 타입 변환 | 0 | {} | `2026-11-20 14:40:35; 2026-11-20 14:40:35; 2026-11-20 14:40:35` | MAP-01;MAP-02;MAP-04;MAP-05;MAP-10 |
| `_SRC_ROW_NO` | `int64` | Bronze 행 번호 | Bronze의 1부터 시작하는 행 번호 | 0 | {} | `1; 2; 3` | TRACE-01 |
| `_SRC_BRONZE_FILE` | `string` | Bronze 상대 경로 | 입력 루트 기준 Bronze 상대 경로 | 0 | {} | `event/race_change_events.parquet; event/race_change_events.parquet; event/race_change_events.parquet` | TRACE-01 |
