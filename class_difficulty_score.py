import pandas as pd
import streamlit as st
import altair as alt

st.set_page_config(
    page_title="VT Class Dashboard",
    layout="wide"
)

@st.cache_data
def load_data(path="grades2.csv"):
    df = pd.read_csv(path)
    grade_cols = [
        'A (%)','A- (%)','B+ (%)','B (%)','B- (%)',
        'C+ (%)','C (%)','C- (%)','D+ (%)','D (%)',
        'D- (%)','F (%)'
    ]
    for col in grade_cols + ['GPA','Withdraws','Graded Enrollment','Credits']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df['Course No.'] = df['Course No.'].astype(int).astype(str)
    return df.round(2), grade_cols

@st.cache_data
def load_course_info(path="vt_courses.csv"):
    ci = pd.read_csv(path)
    mask = ci['number'].astype(str).str.fullmatch(r'\d+')
    ci = ci.loc[mask].copy()
    ci['Course No.'] = ci['number'].astype(int).astype(str)
    ci = (
        ci
        .rename(columns={
            'subject':'Subject',
            'title':'Course Description Title',
            'credits':'Credits',
        })
        [['Subject','Course No.','Course Description Title','Credits',
          'description','prerequisites','corequisites','contact_hours','pathways']]
    )
    return ci

df, grade_cols = load_data()
course_info = load_course_info()

# preparing merged dataframe for compare section
@st.cache_data
def prepare_compare_df(df, course_info, grade_cols):
    # preparing merged dataframe for compare section
    merge_cols = ['Subject', 'Course No.']
    df_avg_merge = df.groupby(merge_cols, as_index=False)[grade_cols].mean()
    df_meta_merge = (
        df
        .groupby(merge_cols, as_index=False)
        .agg({'Course Title':'first','GPA':'mean'})
    )
    dfc = pd.merge(df_meta_merge, df_avg_merge, on=merge_cols).round(2)
    dfc = (
        dfc
        .merge(course_info, on=merge_cols, how='left')
        .fillna({
            'Course Description Title':'',
            'Credits':'',
            'description':'',
            'prerequisites':'',
            'corequisites':'',
            'contact_hours':'',
            'pathways':''
        })
    )
    dfc['CourseKey'] = dfc['Subject'] + " " + dfc['Course No.']
    return dfc

df_compare = prepare_compare_df(df, course_info, grade_cols)

# making course title appear and creating real-time lookup for compare
key2label = {
    key: f"{title} ({key})"
    for key, title in zip(
        df_compare['CourseKey'],
        df_compare['Course Title']
    )
}

@st.cache_data
def get_grade_melt(course_key):
    sub, num = course_key.split()
    melt = (
        df_compare
        .query("Subject == @sub and `Course No.` == @num")
        [grade_cols]
        .melt(var_name="Grade", value_name="Percent")
    )
    melt["Course"] = course_key
    return melt

# creating tabs
view = st.radio("", ["Dashboard", "Compare"], horizontal=True)

if view == "Dashboard":
    # group by professor option
    group_mode = st.sidebar.radio(
        "Professor grouping",
        ("Merge professors", "Separate professors")
    )

    # aggregating data
    if group_mode == "Merge professors":
        group_cols = ['Subject', 'Course No.']
    else:
        group_cols = ['Subject', 'Course No.', 'Instructor']

    df_avg = df.groupby(group_cols, as_index=False)[grade_cols].mean()
    df_meta = (
        df
        .groupby(group_cols, as_index=False)
        .agg({'Course Title':'first','GPA':'mean'})
    )
    df_combined = pd.merge(df_meta, df_avg, on=group_cols).round(2)
    df_combined = (
        df_combined
        .merge(course_info, on=['Subject','Course No.'], how='left')
        .fillna({
            'Course Description Title':'',
            'Credits':'',
            'description':'',
            'prerequisites':'',
            'corequisites':'',
            'contact_hours':'',
            'pathways':''
        })
    )
    df_combined['CourseKey'] = df_combined['Subject'] + " " + df_combined['Course No.']

    # building disply table
    if group_mode == "Separate professors":
        display_cols = ['Subject','Course No.','GPA','Instructor','Course Title'] + grade_cols
    else:
        display_cols = ['Subject','Course No.','Course Title','GPA'] + grade_cols

    # sidebar filters
    all_depts = sorted(df_combined['Subject'].unique())
    dept_options = ["Select all"] + all_depts
    selected_departments = st.sidebar.multiselect(
        "Department", dept_options, default=[]
    )
    if "Select all" in selected_departments:
        selected_departments = all_depts

    # determine available CourseKey options
    if selected_departments:
        available_course_keys = sorted(
            df_combined[
                df_combined['Subject'].isin(selected_departments)
            ]['CourseKey']
            .unique()
        )
    else:
        available_course_keys = []

    # helper for sidebar course display
    def format_course_key(key):
        if key == "Select all":
            return key
        title = df_combined.loc[
            df_combined['CourseKey'] == key,
            'Course Title'
        ].iat[0]
        return f"{title} ({key})"

    course_options = ["Select all"] + available_course_keys
    selected_course_keys = st.sidebar.multiselect("Course", course_options, default=[], format_func=format_course_key)
    if "Select all" in selected_course_keys:
        selected_course_keys = available_course_keys

    # filtering by department + CourseKey
    mask = df_combined['Subject'].isin(selected_departments)
    if selected_course_keys:
        mask &= df_combined['CourseKey'].isin(selected_course_keys)
    df_display = df_combined.loc[mask, display_cols].reset_index(drop=True)

    # displaying aggregated table
    if not selected_departments:
        title = "No department selected"
    elif len(selected_departments) == 1:
        title = selected_departments[0]
    else:
        title = f"{len(selected_departments)} departments"

    st.subheader(f"{title} — {len(df_display):,} courses")
    st.dataframe(
        df_display,
        column_config={
            "Course Title": st.column_config.TextColumn(
                label="Course Title",
                width="medium"
            )
        },
        use_container_width=True
    )

    # CHARTS

    # lookup full merged table and details when 1 course selected
    if df_display.shape[0] == 1:
        sel = df_display.iloc[0]
        mask = (
            (df_combined['Subject']   == sel['Subject'])
            & (df_combined['Course No.'] == sel['Course No.'])
        )
        if group_mode == "Separate professors":
            mask &= (df_combined['Instructor'] == sel['Instructor'])
        full_row = df_combined.loc[mask].iloc[0]

        # bar distribution
        grade_melt = df_display.melt(
            id_vars=group_cols,
            value_vars=grade_cols,
            var_name='Grade',
            value_name='Percent'
        )

        st.subheader(
            f"{full_row['Course Title']} ({full_row['Subject']} {full_row['Course No.']}) Grade Distribution"
        )

        custom_colors = [
            '#53a4f5',
            '#1a84b8',
            '#c4b3a6',
            '#d0a77c',
            '#e8cbae',
            '#1aa4b8',
            '#21af94',
            '#429593',
            '#dfdac4',
            '#b0a384',
            '#c9c1a7',
            '#948363'
        ]

        bar = (
            alt.Chart(grade_melt)
            .mark_bar()
            .encode(
                x=alt.X(
                    "Grade:N",
                    sort=grade_cols,
                    axis=alt.Axis(labelAngle=0, labelAlign="center")),
                y=alt.Y("Percent:Q", title="Average %"),
                color=alt.Color(
                    "Grade:N",
                    sort=grade_cols,
                    scale=alt.Scale(
                        domain=grade_cols,
                        range=custom_colors
                    )
                ),
                tooltip=group_cols + ["Grade", "Percent"]
            )
        )

        gpa_df = pd.DataFrame({
            'label': ['GPA'],
            'GPA': [full_row['GPA']]
        })

        gpa_chart = (
            alt.Chart(gpa_df)
            .mark_bar(size=60, color='#d471f5')
            .encode(
                x=alt.X(
                    'label:O',
                    axis=alt.Axis(
                        title=f"{full_row['Subject']} {full_row['Course No.']}",
                        labels=False,
                        ticks=False
                    )
                ),
                y=alt.Y(
                    'GPA:Q',
                    title='GPA',
                    scale=alt.Scale(domain=[0, 4])
                ),
                tooltip=alt.Tooltip('GPA:Q', format='.2f')
            )
            .properties(
                width=80,
                height=300
            )
        )

        combo = alt.hconcat(
            bar.properties(width=600, height=300),
            gpa_chart
        ).resolve_scale(y='independent')

        st.altair_chart(combo, use_container_width=True)

        # pull out all the info fields
        desc = full_row.get('description', '')
        prereq = full_row.get('prerequisites', '')
        coreq = full_row.get('corequisites', '')
        chours = full_row.get('contact_hours', '')
        path = full_row.get('pathways', '')
        subtitle = full_row.get('Course Description Title', '')

        with st.expander("📖 Course Details", expanded=True):
            st.markdown(f"**{full_row['Course Title']}**  ")
            if subtitle and subtitle != full_row['Course Title']:
                st.markdown(f"*Subtitle:* {subtitle}  ")
            st.markdown(f"**Credits:** {full_row.get('Credits','–')}  ")
            if desc:
                st.markdown(f"**Description:**  \n{desc}")
            if prereq:
                st.markdown(f"**Prerequisites:** {prereq}")
            if coreq:
                st.markdown(f"**Corequisites:** {coreq}")
            if chours:
                st.markdown(f"**Contact hours:** {chours}")
            if path:
                st.markdown(f"**Pathways:** {path}")

        # # pie distribution
        # st.subheader(f"{full_row['Course No.']} Grade Distribution (pie)")
        # pie_data = grade_melt.copy()
        #
        # # preserve display order
        # pie_data['Grade'] = pd.Categorical(
        #     pie_data['Grade'],
        #     categories=grade_cols,
        #     ordered=True
        # )
        # pie_data['rank'] = pie_data['Grade'].map({g: i for i, g in enumerate(grade_cols)})
        #
        # pie = (
        #     alt.Chart(pie_data)
        #     .mark_arc()
        #     .encode(
        #         theta=alt.Theta("Percent:Q", stack="normalize"),
        #         color=alt.Color("Grade:N", title="Grade", sort=grade_cols),
        #         order=alt.Order("rank:Q", sort="ascending"),
        #         tooltip=group_cols + ["Grade", "Percent"]
        #     )
        # )
        # st.altair_chart(pie, use_container_width=True)

    else:
        st.info("Select exactly one course to view its bar distribution chart and details.")

# Compare tab
elif view == "Compare":
    course_keys = sorted(df_compare['CourseKey'].unique())
    course1_list = st.sidebar.multiselect(
        "Course #1",
        course_keys,
        default = [],
        format_func = lambda k: key2label[k]
    )
    course1 = course1_list[0] if course1_list else None

    course2_list = st.sidebar.multiselect(
        "Course #2",
        course_keys,
        default = [],
        format_func = lambda k: key2label[k]
    )
    course2 = course2_list[0] if course2_list else None

    st.header("Compare Two Courses")

    if not course1 or not course2:
        st.info("Select two courses on the left to see a side‑by‑side bar chart of their grade distributions.")
    else:
        m1 = get_grade_melt(course1)
        m2 = get_grade_melt(course2)

        compare_df = pd.concat([m1, m2], ignore_index=True)

        bar = (
            alt.Chart(compare_df)
            .mark_bar()
            .encode(
                x=alt.X(
                    "Grade:N",
                    sort=grade_cols,
                    axis=alt.Axis(labelAngle=0, labelAlign="center")
                ),
                y=alt.Y("Percent:Q", title="Average %"),
                color=alt.Color(
                    "Course:N",
                    title="Course",
                    scale=alt.Scale(domain=[course1, course2], range=["#53a4f5", "#21af94"])
                ),
                xOffset=alt.XOffset("Course:N")
            )
        )

        gpa_comp_df = (
            df_compare
            .loc[df_compare['CourseKey'].isin([course1, course2]), ['CourseKey', 'GPA']]
            .rename(columns={'CourseKey': 'Course'})
        )

        # gpa compare chart
        gpa_compare_chart = (
            alt.Chart(gpa_comp_df)
            .mark_bar(size=60)
            .encode(
                x=alt.X('Course:N', axis=alt.Axis(labelAngle=0, labelAlign='center')),
                y=alt.Y('GPA:Q', title='GPA', scale=alt.Scale(domain=[0, 4])),
                color=alt.Color(
                    'Course:N',
                    title='Course',
                    scale=alt.Scale(
                        domain=[course1, course2],
                        range=['#53a4f5', '#d0a77c']
                    )
                ),
                tooltip=[
                    alt.Tooltip('Course:N', title='Course'),
                    alt.Tooltip('GPA:Q', format='.2f')
                ]
            )
            .properties(
                width=150,
                height=300
            )
        )

        combo = alt.hconcat(
            bar.properties(width=650, height=300),
            gpa_compare_chart
        ).resolve_scale(y='independent')

        st.altair_chart(combo, use_container_width=True)
