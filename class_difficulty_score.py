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

# group by professor option
group_mode = st.sidebar.radio(
    "Professor grouping",
    ("Merge professors", "Separate professors")
)

if group_mode == "Merge professors":
    group_cols = ['Subject', 'Course No.']
else:
    group_cols = ['Subject', 'Course No.', 'Instructor']

# aggregating data
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

# building disply table
if group_mode == "Separate professors":
    display_cols = ['Subject','Course No.','GPA','Instructor','Course Title'] + grade_cols
else:
    display_cols = ['Subject','Course No.','Course Title','GPA'] + grade_cols

df_display = df_combined[display_cols]

# sidebar filters
all_depts   = sorted(df_combined['Subject'].unique())
all_courses = sorted(df_combined['Course No.'].unique())

# multiselect & select all
dept_options        = ["Select all"] + all_depts
selected_departments = st.sidebar.multiselect(
    "Department", dept_options, default=[]
)
if "Select all" in selected_departments:
    selected_departments = all_depts
if selected_departments:
    available_courses = sorted(
        df_combined[df_combined['Subject'].isin(selected_departments)]
        ['Course No.']
        .unique()
    )
else:
    available_courses = []
course_options    = ["Select all"] + available_courses
selected_courses  = st.sidebar.multiselect(
    "Course No.", course_options, default=[]
)
if "Select all" in selected_courses:
    selected_courses = available_courses

# filtering
df_display = df_combined[display_cols].copy()
df_display = df_display[
    df_display['Subject'].isin(selected_departments) &
    df_display['Course No.'].isin(selected_courses)
].reset_index(drop=True)

# displaying aggregated table
if not selected_departments:
    title = "No department selected"
elif len(selected_departments) == 1:
    title = selected_departments[0]
else:
    title = f"{len(selected_departments)} departments"

st.subheader(f"{title} — {len(df_display):,} courses")
st.dataframe(df_display)

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

    st.subheader(f"{df_display.iloc[0]['Course No.']} Grade Distribution (bar)")

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
    # st.altair_chart(bar, use_container_width=True)

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
    desc     = full_row.get('description', '')
    prereq   = full_row.get('prerequisites', '')
    coreq    = full_row.get('corequisites', '')
    chours   = full_row.get('contact_hours', '')
    path     = full_row.get('pathways', '')
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
    # st.subheader(f"{df_display.iloc[0]['Course No.']} Grade Distribution (pie)")
    # pie_data = grade_melt.copy()
    #
    # # preserving display order
    # pie_data['Grade'] = pd.Categorical(
    #     pie_data['Grade'],
    #     categories=grade_cols,
    #     ordered=True
    # )
    #
    # rank_map = {g: i for i, g in enumerate(grade_cols)}
    # pie_data['rank'] = pie_data['Grade'].map(rank_map)
    #
    # # pie data
    # pie = (
    #     alt.Chart(pie_data)
    #     .mark_arc()
    #     .encode(
    #         theta=alt.Theta("Percent:Q", stack="normalize"),
    #         color=alt.Color("Grade:N", title="Grade", sort=grade_cols),
    #         order=alt.Order("rank:Q", sort="ascending"),
    #         tooltip=group_cols + ["Grade","Percent"]
    #     )
    # )
    # st.altair_chart(pie, use_container_width=True)

else:
    st.info("Select exactly one course to view its bar distribution chart and details.")