import pathlib
from dash import Dash, html, dcc, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# read data
PATH = pathlib.Path(__file__).parent
DATA_PATH = PATH.joinpath("data").resolve()
df = pd.read_excel(DATA_PATH.joinpath("Trade.xlsx"))

# initial data cleanning
df.rename(columns={df.columns[0]:'Quarter'}, inplace=True)
df.rename(columns={df.columns[1]:'Region'}, inplace=True)
df.rename(columns={df.columns[2]:'Information'}, inplace=True)

df['Quarter'].ffill(inplace=True)
df['Region'].ffill(inplace=True)

df = df[~df['Information'].str.contains('origin|consignment', case=False)]
df = df.reset_index(drop=True)

value_mapping = {
    'Export, millions of euro': 'Export',
    'Import, millions of euro': 'Import'
}

df['Information'] = df['Information'].replace(value_mapping)

# prepare data from first graph
trade_total = df[['Quarter', 'Information', 'Region', 'GS Goods and services', 'G Goods', 'S Services']]

# calculate the trade balance and sum
groups = trade_total.groupby(['Quarter', 'Region'])
new_rows = []

for category in ['GS Goods and services', 'G Goods', 'S Services']:
    for (q, r), group in groups:
        export_str = group[group['Information'] == 'Export'][category].values[0]
        import_str = group[group['Information'] == 'Import'][category].values[0]

        try:
            export_value = int(export_str)
        except ValueError:
            export_value = 0
        try:
            import_value = int(import_str)
        except ValueError:
            import_value = 0

        balance = export_value - import_value
        total = export_value + import_value

        balance_row = pd.DataFrame({
            'Quarter': [q],
            'Information': 'Balance',
            'Region': [r],
            category: balance
        })

        sum_row = pd.DataFrame({
            'Quarter': [q],
            'Information': 'Sum',
            'Region': [r],
            category: total
        })

        new_rows.append(balance_row)
        new_rows.append(sum_row)

trade_total = pd.concat([trade_total] + new_rows, ignore_index=True)
trade_total = trade_total.groupby(['Quarter', 'Region', 'Information']).sum().reset_index()


#### dataframe 1 ####
# transform the trading amount from quarter to year
trade_total['Year'] = trade_total['Quarter'].str.extract('(\d{4})')
trade_per_year = trade_total.drop('Quarter', axis=1)
numeric_columns = ['Year', 'GS Goods and services', 'G Goods', 'S Services']
trade_per_year[numeric_columns] = trade_per_year[numeric_columns].apply(pd.to_numeric, errors='coerce')
trade_per_year = trade_per_year.groupby(['Year', 'Region', 'Information']).sum().reset_index()
trade_per_year = trade_per_year.drop(trade_per_year[trade_per_year['Year'] == 2023].index)
trade_per_year = trade_per_year.rename(columns={"GS Goods and services": "Goods and Services", "G Goods": "Goods", "S Services": "Services"})


# #### dataframe 2 ####
trade_by_region = trade_per_year
regions_to_drop = ['Foreign countries, total',
                   'Other countries excl. EU(27, 2020-)',
                   'Other countries excl. EU (28, 2013-2020)',
                   'EU countries (27, 2020-)',
                   'EU countries (28, 2013-2020)',
                   'Euro area (19, 2015-2022)',
                   'Other countries excl. Euro area (19, 2015-2022)',
                   'Euro area (20, 2023-)',
                   'Other countries excl. Euro area (20, 2023-)',
                   'Europe',
                   'Africa',
                   'America',
                   'Asia',
                   'Oceania and polar regions'] 
trade_by_region = trade_by_region.drop(trade_by_region[trade_by_region['Region'].isin(regions_to_drop)].index)
trade_by_region = pd.melt(trade_by_region, id_vars=['Year', 'Region', 'Information'], var_name='Category', value_name='Value')
trade_by_region = trade_by_region.pivot_table(index=['Year', 'Region', 'Category'], columns='Information', values='Value', aggfunc='first').reset_index()


#### dataframe 3 ####
trade_by_continent = trade_per_year.loc[trade_per_year['Region'].isin(['Africa', 'America', 'Asia', 'Europe', 'Oceania and polar regions'])]
trade_by_continent = trade_by_continent[trade_by_continent['Information'].isin(['Import', 'Export'])]
trade_by_continent = pd.melt(trade_by_continent, id_vars=['Year', 'Region', 'Information'], var_name='Category', value_name='Value')
trade_by_continent = trade_by_continent.pivot_table(index=['Year', 'Region', 'Category'], columns='Information', values='Value').reset_index()


#### dataframe 4 ####
trade_by_category = df[(df['Region'] == 'Foreign countries, total')]
trade_by_category['Year'] = trade_by_category['Quarter'].str.extract('(\d{4})')
trade_by_category = trade_by_category.drop(['Quarter', 'Region', 'SJ Other business services', 'GS Goods and services', 'S Services'], axis=1)
all_columns = trade_by_category.columns
filtered_columns = [col for col in all_columns if col != 'Information']
trade_by_category[filtered_columns] = trade_by_category[filtered_columns].apply(pd.to_numeric, errors='coerce')
trade_by_category = trade_by_category.groupby(['Information', 'Year']).sum().reset_index()
trade_by_category = trade_by_category.sort_values(by=['Year', 'Information']).reset_index(drop=True)
trade_by_category = trade_by_category.drop(trade_by_category[trade_by_category['Year'] == 2023].index)
filter = [col for col in all_columns if col not in ['Information', 'Year']]
trade_by_category = trade_by_category.melt(id_vars=['Information', 'Year'], value_vars=filter, var_name='Category', value_name='Value')

def add_parent(category):
    if category.startswith('G'):
        return 'Goods'
    elif category.startswith('S'):
        return 'Services'

trade_by_category['Parent'] = trade_by_category['Category'].apply(add_parent)
trade_by_category['Category'] = trade_by_category['Category'].apply(lambda x: x[2:] if x.startswith('G') else x[3:])
trade_by_category['Category'] = trade_by_category['Category'].str.strip()
trade_by_category = trade_by_category.sort_values(by=['Year', 'Category']).reset_index(drop=True)

value_mapping = {'Manufacturing services on physical inputs owned by others': 'Manufacturing',
                 'Maintenance and repair services not included elsewhere': 'Maintenance',
                 'Insurance and pension services': 'Insurance & pension',
                 'Charges for the use of intellectual property n.i.e.': 'Use of intellectual property',
                 'Telecommunications, computer and information services': 'ICT',
                 'Research and development services': 'R & D',
                 'Professional and management consulting services': 'Professional & management consulting',
                 'Technical, trade-related, and other business services': 'Technical, trade-related services',
                 'Personal, cultural and recreational services': 'Culture & recreation',
                 'Government goods and services n.i.e': 'Government'}

trade_by_category['Category'] = trade_by_category['Category'].replace(value_mapping)


#### create Dash app ####
app = Dash(external_stylesheets=[dbc.themes.FLATLY])
server = app.server

sidebar = html.Div([
    dbc.Row(
        [
            html.H2(html.B("International Trade Dashboard"), className="mt-4 ml-5")
            ],
        style={"height": "20vh"}, className='bg-primary text-white'
        ),
    dbc.Row(
        [
            html.P("This interactive dashboard provides a comprehensive overview of Finland's international trade activities over the past decade. " +
                   "There are 4 different visualizations, showcasing the overall trend of internation trade, top trading partners, trade distribution across continents, and trade breakdown by categories.")
            ],
        style={"height": "27vh", "margin": "20px 5px 20px 5px", "line-height": "1.6"}
        ),
    dbc.Row(
        [
            html.H6(html.B("Settings"), className="ml-5"),
        ],
        style={"margin-left": "5px"}
        ),
    dbc.Row(
        [
            html.P("Select type of trade:"),
            dcc.Dropdown(['All', 'Import', 'Export'], 'All', id='info-dropdown'),
        ],
        style={"margin-left": "5px", "margin-right": "5px", "margin-top": "15px"}
        ),
    dbc.Row(
        [
            html.P("Select category of trade:"),
            dcc.Dropdown(['Goods and Services', 'Goods', 'Services'], 'Goods and Services', id='category-dropdown'),
        ],
        style={"margin-left": "5px", "margin-right": "5px", "margin-top": "25px"}
        ),
    dbc.Row(
        [
            html.P("Year slider:"),
            dcc.Slider(
                trade_per_year['Year'].min(),
                trade_per_year['Year'].max(),
                step=None,
                value=trade_per_year['Year'].max(),
                marks={str(year): str(year) for year in trade_per_year['Year'].unique()},
                id='year-slider',
                included=False
            )
        ],
        style={"margin-left": "5px", "margin-right": "5px", "margin-top": "25px"}
        )
])

content = html.Div(
    [
        dbc.Row(
            [
                dbc.Col([
                        html.Div([
                            # html.P(html.B("Internation Trade in Goods and Services"), className="mt-3"),
                            dcc.Graph(id="graph1")])
                        ]),
                dbc.Col([
                        html.Div([
                            # html.P(html.B("Top Trading Partners"), className="mt-3"),
                            dcc.Graph(id="graph2")])
                        ])
            ],
            style={"height": "50vh"}
        ),
        
        dbc.Row(
            [
                dbc.Col([
                        html.Div([
                            # html.P(html.B("Import and Export by Continents"), className="mt-3"),
                            dcc.Graph(id="graph3")])
                        ]),
                dbc.Col([
                        html.Div([
                            # html.P(html.B("Trading by Categories"), className="mt-3"),
                            dcc.Graph(id="graph4")])
                        ])
            ],
            style={"height": "50vh"}
        )
    ]
)

app.layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(sidebar, width=3, className='bg-light'),
                dbc.Col(content, width=9)
                ],
            style={"height": "100vh"}
            )
        ],
    fluid=True
    )


@app.callback(
    [Output(component_id='graph1', component_property='figure'),
     Output(component_id='graph2', component_property='figure'),
     Output(component_id='graph3', component_property='figure'),
     Output(component_id='graph4', component_property='figure')],
    [Input(component_id='year-slider', component_property='value'),
     Input(component_id='info-dropdown', component_property='value'),
     Input(component_id='category-dropdown', component_property='value')]
)

def update_graph(selected_year, selected_info, selected_category):
    df1 = trade_per_year[trade_per_year['Region'] == 'Foreign countries, total']
    df2 = trade_by_region[trade_by_region['Year'] == selected_year]
    df2 = df2[df2['Category'] == selected_category]
    df3 = trade_by_continent[trade_by_continent['Year'] == selected_year]
    df3 = df3[df3['Category'] == selected_category]
    df4 = trade_by_category[trade_by_category['Year'] == selected_year]

    if (selected_info != 'All'):
        df1 = df1[df1['Information'] == selected_info]
        df2 = df2.sort_values(by=selected_info, ascending=False).head(20)
        df4 = df4[df4['Information'] == selected_info]
    else:
        df2 = df2.sort_values(by='Sum', ascending=False).head(20)

    if (selected_category != 'Goods and Services'): 
        df4 = df4[df4['Parent'] == selected_category]


    #### fig 1####
    fig1 = px.line(df1,
                   x='Year',
                   y=selected_category,
                   color='Information',
                   markers=True,
                   color_discrete_map={
                    'Sum': '#AB63FA',
                    'Balance': '#00CC96',
                    'Import': '#EF553B',
                    'Export': '#636EFA'})
    
    if (selected_info != 'All'):
        fig1.update_layout(title = f'{selected_info} in {selected_category}')
    else:
        fig1.update_layout(title = f'International Trade in {selected_category}')

    fig1.update_xaxes(tickangle=45, dtick=1)
    fig1.update_layout(width=540,
                      height=360,
                      yaxis_title = '',
                      title = {'y': 0.9},
                      margin=dict(l=0, r=0, t=70, b=0))
        
        
    #### fig 2####    
    if (selected_info == 'Import'):
        fig2 = px.bar(df2, x='Region', y=selected_info, color_discrete_sequence=['#EF553B'],
                      title=f'Top {selected_info} Partners in {selected_category} ({selected_year})')
    elif (selected_info == 'Export'):
        fig2 = px.bar(df2, x='Region', y=selected_info,
                      title=f'Top {selected_info} Partners in {selected_category} ({selected_year})')
    else:
        fig2 = px.bar(df2, x='Region', y=['Export', 'Import'], 
                labels={'value': 'Import and Export', 'variable': 'Type'},
                title=f'Top Trading Partners in {selected_category} ({selected_year})',
                barmode='stack')
    fig2.update_xaxes(tickangle=45)
    fig2.update_layout(width=540,
                      height=360,
                      yaxis_title = '',
                      title = {'y': 0.9},
                      margin=dict(l=0, r=0, t=70, b=0))
    

    #### fig 3####
    fig3 = make_subplots(rows=1, cols=2, specs=[[{"type": "pie"}, {"type": "pie"}]], subplot_titles=['Import', 'Export'])

    fig3.add_trace(go.Pie(
        values=df3['Import'],
        labels=df3['Region'],
        name='Import'), 
        row=1, col=1)

    fig3.add_trace(go.Pie(
        values=df3['Export'],
        labels=df3['Region'],
        name='Export'),
        row=1, col=2)

    fig3.update_layout(width=540,
                    height=360,
                    margin=dict(l=55, r=0, t=100, b=80),
                    title={'text': f'Trade by Continents in {selected_category} ({selected_year})', 'y': 0.9})
    
    if (selected_info == 'Import'):
        fig3.update_traces(opacity=0.3, showlegend=False, textinfo='none', selector=dict(name='Export'))
        fig3.update_layout(title=f'{selected_info} by Continents in {selected_category} ({selected_year})')
    elif (selected_info == 'Export'):
        fig3.update_traces(opacity=0.3, showlegend=False, textinfo='none', selector=dict(name='Import'))
        fig3.update_layout(title=f'{selected_info} by Continents in {selected_category} ({selected_year})')
    

    #### fig 4####
    fig4 = px.treemap(df4, 
                 path=['Parent', 'Category'],
                 values='Value')

    if (selected_category=='Goods'):
        fig4.update_layout(treemapcolorway = ['#636EFA'])
    elif (selected_category == 'Services'):
        fig4.update_layout(treemapcolorway = ['#EF553B'])
    else:
        fig4.update_layout(treemapcolorway = ['#636EFA', '#EF553B'])
    
    if (selected_info != 'All'):
        fig4.update_layout(title = f'{selected_info} by Categories ({selected_year})')
    else:
        fig4.update_layout(title = f'Trade by Categories ({selected_year})')

    fig4.update_layout(width=540,
                      height=360,
                      margin = dict(l=20, r=30, t=70, b=30),
                      title = {'y': 0.9})

    return fig1, fig2, fig3, fig4

if __name__ == '__main__':
    app.run_server(debug=False)