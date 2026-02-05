import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from google.ads.googleads.client import GoogleAdsClient
from datetime import datetime
from dateutil.relativedelta import relativedelta
import yaml
import tempfile
import os
import time
import requests
import base64

# Page config
st.set_page_config(page_title="Multi-Platform Share of Search", page_icon="📊", layout="wide")

st.title("📊 Multi-Platform Share of Search Analysis")
st.caption("Track Share of Search across Google and Amazon")

# Initialize session state
if 'google_results' not in st.session_state:
    st.session_state.google_results = None
if 'amazon_results' not in st.session_state:
    st.session_state.amazon_results = None

# Sidebar - Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Platform Selection
    st.subheader("Select Platforms")
    include_google = st.checkbox("Google Search", value=True)
    include_amazon = st.checkbox("Amazon Search", value=True)
    
    if not include_google and not include_amazon:
        st.error("Select at least one platform")
    
    st.markdown("---")
    
    # Google Ads API Configuration
    if include_google:
        st.subheader("1️⃣ Google Ads API")
        with st.expander("ℹ️ How to get Google Ads credentials", expanded=False):
            st.markdown("""
            **Required:**
            - Developer token from Google Ads API Center
            - OAuth credentials (Client ID, Secret, Refresh Token)
            - Customer ID (your Google Ads account)
            - Login Customer ID (MCC) if using manager account
            
            **Upload a google-ads.yaml file with:**
            ```yaml
            developer_token: YOUR_DEV_TOKEN
            client_id: YOUR_CLIENT_ID
            client_secret: YOUR_CLIENT_SECRET
            refresh_token: YOUR_REFRESH_TOKEN
            customer_id: YOUR_CUSTOMER_ID
            login_customer_id: YOUR_MCC_ID  # if using MCC
            use_proto_plus: True
            ```
            """)
        
        google_yaml = st.file_uploader("Upload google-ads.yaml", type=['yaml', 'yml'], key='google_yaml')
        
        if google_yaml:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.yaml', mode='wb') as tmp:
                tmp.write(google_yaml.getvalue())
                tmp_path = tmp.name
            
            with open(tmp_path, 'r') as f:
                google_config = yaml.safe_load(f)
            
            google_customer_id = st.text_input("Google Customer ID", value=google_config.get('customer_id', ''), key='google_cust')
            os.unlink(tmp_path)
            st.success("✅ Google Ads configured")
        else:
            google_customer_id = None
            st.info("Upload google-ads.yaml to enable Google SoS")
        
        st.markdown("---")
    
    # DataforSEO API Configuration
    if include_amazon:
        st.subheader("2️⃣ DataforSEO API (Amazon)")
        with st.expander("ℹ️ How to get DataforSEO credentials", expanded=False):
            st.markdown("""
            **Steps:**
            1. Sign up at [DataforSEO.com](https://dataforseo.com/)
            2. Go to Dashboard → API Access
            3. Copy your Login (email) and Password (API key)
            
            **Pricing:**
            - Pay-as-you-go: ~$0.10-0.50 per keyword
            - No monthly subscription required
            - First $1 free for testing
            
            **What you'll get:**
            - Amazon search volume data
            - Monthly trends
            - Keyword difficulty scores
            """)
        
        dataforseo_login = st.text_input("DataforSEO Login (email)", key='dataforseo_login')
        dataforseo_password = st.text_input("DataforSEO Password (API key)", type="password", key='dataforseo_pass')
        
        if dataforseo_login and dataforseo_password:
            st.success("✅ DataforSEO configured")
        else:
            st.info("Enter DataforSEO credentials to enable Amazon SoS")
        
        st.markdown("---")
    
    # Analysis Settings
    st.subheader("3️⃣ Analysis Settings")
    target_brand = st.text_input("🎯 Target Brand", value="LampTwist")
    
    competitor_brands_text = st.text_area(
        "🏁 Competitor Brands (one per line)",
        value="MOHD\nLa Redoute\nwest elm\nWayfair",
        height=150
    )
    competitor_brands = [b.strip() for b in competitor_brands_text.split('\n') if b.strip()]
    
    st.subheader("4️⃣ Settings")
    months_back = st.slider("📅 Months of data", 3, 12, 12)
    
    if include_google:
        country = st.selectbox("🌍 Country (Google)", ["Belgium", "United States", "United Kingdom", "France", "Germany"])
        language = st.selectbox("🗣️ Language (Google)", ["English", "French", "Dutch", "German", "Spanish"])
    
    if include_amazon:
        amazon_marketplace = st.selectbox(
            "🛒 Amazon Marketplace",
            ["amazon.com (US)", "amazon.co.uk (UK)", "amazon.de (Germany)", "amazon.fr (France)", "amazon.it (Italy)", "amazon.es (Spain)"]
        )
    
    st.markdown("---")
    run_button = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

# Country and language mappings for Google
COUNTRIES = {
    "Belgium": "2056", "United States": "2840", "United Kingdom": "2826",
    "France": "2250", "Germany": "2276"
}

LANGUAGES = {
    "English": "1000", "French": "1002", "Dutch": "1010",
    "German": "1003", "Spanish": "1003"
}

# Amazon marketplace codes for DataforSEO
AMAZON_LOCATIONS = {
    "amazon.com (US)": "2840",
    "amazon.co.uk (UK)": "2826",
    "amazon.de (Germany)": "2276",
    "amazon.fr (France)": "2250",
    "amazon.it (Italy)": "2380",
    "amazon.es (Spain)": "2724"
}

# Google Ads Functions
def get_google_keyword_volumes(client, customer_id, brand, location_id, language_id, months_back):
    """Get keyword search volumes from Google Ads API with monthly breakdown"""
    
    try:
        # Calculate date range - 2 month buffer
        end_date = datetime.now().replace(day=1) - relativedelta(months=2)
        start_date = end_date - relativedelta(months=months_back - 1)
        
        # Services
        keyword_service = client.get_service("KeywordPlanIdeaService")
        geo_service = client.get_service("GeoTargetConstantService")
        
        # Build request
        request = client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = customer_id
        request.language = client.get_service("GoogleAdsService").language_constant_path(language_id)
        request.geo_target_constants = [geo_service.geo_target_constant_path(location_id)]
        request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
        request.keyword_seed.keywords.append(brand.lower())
        
        # Historical metrics
        request.historical_metrics_options.year_month_range.start.year = start_date.year
        request.historical_metrics_options.year_month_range.start.month = start_date.month
        request.historical_metrics_options.year_month_range.end.year = end_date.year
        request.historical_metrics_options.year_month_range.end.month = end_date.month
        
        # Get ideas
        response = keyword_service.generate_keyword_ideas(request=request)
        
        # Process results
        monthly_volumes = {}
        total_avg = 0
        keywords = []
        
        for idea in response:
            if brand.lower() in idea.text.lower():
                metrics = idea.keyword_idea_metrics
                total_avg += metrics.avg_monthly_searches or 0
                keywords.append(idea.text)
                
                if metrics.monthly_search_volumes:
                    for mv in metrics.monthly_search_volumes:
                        month_key = f"{mv.year}-{mv.month:02d}"
                        monthly_volumes[month_key] = monthly_volumes.get(month_key, 0) + (mv.monthly_searches or 0)
        
        return {
            'brand': brand,
            'avg_volume': total_avg,
            'monthly_volumes': monthly_volumes,
            'keywords': keywords
        }
        
    except Exception as e:
        st.error(f"Google API Error for {brand}: {str(e)}")
        return {
            'brand': brand,
            'avg_volume': 0,
            'monthly_volumes': {},
            'keywords': []
        }

# DataforSEO Functions
def get_amazon_keyword_volumes(login, password, brand, location_code, months_back):
    """Get keyword search volumes from Amazon via DataforSEO API"""
    
    try:
        # API endpoint
        url = "https://api.dataforseo.com/v3/keywords_data/amazon/search_volume/live"
        
        # Authentication
        credentials = f"{login}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }
        
        # Request payload
        payload = [{
            "location_code": int(location_code),
            "keywords": [brand.lower()],
            "search_partners": False
        }]
        
        # Make request
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            st.error(f"DataforSEO API Error for {brand}: Status {response.status_code}")
            return {
                'brand': brand,
                'avg_volume': 0,
                'monthly_volumes': {},
                'keywords': []
            }
        
        data = response.json()
        
        # Process results
        if data.get('tasks') and data['tasks'][0].get('result'):
            result = data['tasks'][0]['result'][0]
            
            search_volume = result.get('search_volume', 0)
            
            # DataforSEO doesn't provide monthly breakdown by default
            # We'll use the average for all months
            monthly_volumes = {}
            end_date = datetime.now().replace(day=1) - relativedelta(months=2)
            
            for i in range(months_back):
                month_date = end_date - relativedelta(months=i)
                month_key = f"{month_date.year}-{month_date.month:02d}"
                monthly_volumes[month_key] = search_volume
            
            return {
                'brand': brand,
                'avg_volume': search_volume,
                'monthly_volumes': monthly_volumes,
                'keywords': [brand]  # DataforSEO returns aggregate, not individual keywords
            }
        else:
            return {
                'brand': brand,
                'avg_volume': 0,
                'monthly_volumes': {},
                'keywords': []
            }
        
    except Exception as e:
        st.error(f"Amazon API Error for {brand}: {str(e)}")
        return {
            'brand': brand,
            'avg_volume': 0,
            'monthly_volumes': {},
            'keywords': []
        }

# Visualization Functions
def create_sos_trend_chart(df_monthly, target_brand, title):
    """Create Share of Search trend chart"""
    
    if df_monthly.empty:
        return None
    
    fig = go.Figure()
    
    for brand in df_monthly['brand'].unique():
        brand_data = df_monthly[df_monthly['brand'] == brand].sort_values('month')
        
        fig.add_trace(go.Scatter(
            x=brand_data['month'],
            y=brand_data['share_of_search'],
            mode='lines+markers',
            name=brand,
            line=dict(width=3 if brand == target_brand else 2),
            marker=dict(size=8 if brand == target_brand else 6)
        ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Month",
        yaxis_title="Share of Search (%)",
        hovermode='x unified',
        height=500,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
    )
    
    return fig

def create_comparison_charts(df_avg, target_brand, title_prefix):
    """Create comparison bar and pie charts"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"{title_prefix} - Volume by Brand")
        fig = px.bar(
            df_avg, x='avg_volume', y='brand',
            orientation='h',
            color='is_target',
            color_discrete_map={True: '#FF6B6B', False: '#4ECDC4'},
            text='avg_volume'
        )
        fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
        fig.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader(f"{title_prefix} - Market Share")
        fig = px.pie(
            df_avg, values='avg_volume', names='brand',
            hole=0.3,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        
        # Highlight target brand
        colors = ['#FF6B6B' if brand == target_brand else '#4ECDC4' 
                  for brand in df_avg['brand']]
        fig.update_traces(marker=dict(colors=colors))
        
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

# Main Execution
if run_button:
    
    all_brands = [target_brand] + competitor_brands
    
    # Create tabs
    tabs = []
    if include_google and google_yaml and google_customer_id:
        tabs.append("🔵 Google SoS")
    if include_amazon and dataforseo_login and dataforseo_password:
        tabs.append("🟠 Amazon SoS")
    if len(tabs) > 1:
        tabs.append("🌐 Combined SoS")
    
    if not tabs:
        st.error("❌ Please configure at least one platform's API credentials")
        st.stop()
    
    tab_objects = st.tabs(tabs)
    tab_idx = 0
    
    # ==========================================
    # GOOGLE SOS TAB
    # ==========================================
    
    if include_google and google_yaml and google_customer_id:
        
        with tab_objects[tab_idx]:
            st.header("🔵 Google Search - Share of Search")
            
            with st.spinner("Loading Google Ads client..."):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.yaml', mode='wb') as tmp:
                        tmp.write(google_yaml.getvalue())
                        tmp_path = tmp.name
                    
                    google_client = GoogleAdsClient.load_from_storage(tmp_path, version="v22")
                    os.unlink(tmp_path)
                    
                except Exception as e:
                    st.error(f"Failed to initialize Google Ads client: {e}")
                    google_client = None
            
            if google_client:
                location_id = COUNTRIES[country]
                language_id = LANGUAGES[language]
                
                google_results = []
                progress_bar = st.progress(0)
                status = st.empty()
                
                for i, brand in enumerate(all_brands):
                    status.text(f"Fetching Google data for {brand}... ({i+1}/{len(all_brands)})")
                    
                    data = get_google_keyword_volumes(
                        google_client, google_customer_id.replace('-', ''), brand,
                        location_id, language_id, months_back
                    )
                    google_results.append(data)
                    
                    progress_bar.progress((i + 1) / len(all_brands))
                    
                    if i < len(all_brands) - 1:
                        time.sleep(2)
                
                status.empty()
                progress_bar.empty()
                
                # Process Google results
                if any(r['avg_volume'] > 0 for r in google_results):
                    st.session_state.google_results = google_results
                    
                    df_google_avg = pd.DataFrame([{
                        'brand': r['brand'],
                        'avg_volume': r['avg_volume'],
                        'is_target': r['brand'] == target_brand
                    } for r in google_results])
                    
                    total_volume = df_google_avg['avg_volume'].sum()
                    df_google_avg['share_of_search'] = (df_google_avg['avg_volume'] / total_volume * 100).round(2)
                    df_google_avg = df_google_avg.sort_values('avg_volume', ascending=False).reset_index(drop=True)
                    
                    # Monthly trends
                    monthly_data = []
                    for r in google_results:
                        for month, volume in r['monthly_volumes'].items():
                            monthly_data.append({
                                'brand': r['brand'],
                                'month': month,
                                'volume': volume
                            })
                    
                    df_google_monthly = pd.DataFrame(monthly_data)
                    
                    if not df_google_monthly.empty:
                        monthly_totals = df_google_monthly.groupby('month')['volume'].sum().reset_index()
                        monthly_totals.columns = ['month', 'total']
                        
                        df_google_monthly = df_google_monthly.merge(monthly_totals, on='month')
                        df_google_monthly['share_of_search'] = (df_google_monthly['volume'] / df_google_monthly['total'] * 100).round(2)
                    
                    # Display Google results
                    st.success("✅ Google data collected!")
                    
                    # Key metrics
                    target_row = df_google_avg[df_google_avg['is_target']].iloc[0]
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Google SoS", f"{target_row['share_of_search']:.2f}%")
                    with col2:
                        st.metric("Search Volume", f"{target_row['avg_volume']:,}")
                    with col3:
                        rank = (df_google_avg['avg_volume'] > target_row['avg_volume']).sum() + 1
                        st.metric("Market Rank", f"#{rank}")
                    
                    # Charts
                    st.subheader("📈 Google Trends Over Time")
                    fig = create_sos_trend_chart(df_google_monthly, target_brand, "Google Share of Search Trends")
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    
                    create_comparison_charts(df_google_avg, target_brand, "Google")
                    
                    # Data table
                    with st.expander("📋 View Google Data Table"):
                        display_df = df_google_avg[['brand', 'avg_volume', 'share_of_search']].copy()
                        display_df.columns = ['Brand', 'Avg Monthly Volume', 'Share of Search (%)']
                        st.dataframe(display_df, use_container_width=True)
                        
                        csv = df_google_avg.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "📥 Download Google CSV",
                            csv,
                            f"google_sos_{datetime.now().strftime('%Y%m%d')}.csv",
                            "text/csv"
                        )
                else:
                    st.error("❌ No Google data collected. Check your settings.")
        
        tab_idx += 1
    
    # ==========================================
    # AMAZON SOS TAB
    # ==========================================
    
    if include_amazon and dataforseo_login and dataforseo_password:
        
        with tab_objects[tab_idx]:
            st.header("🟠 Amazon Search - Share of Search")
            
            with st.spinner("Fetching Amazon data via DataforSEO..."):
                location_code = AMAZON_LOCATIONS[amazon_marketplace]
                
                amazon_results = []
                progress_bar = st.progress(0)
                status = st.empty()
                
                for i, brand in enumerate(all_brands):
                    status.text(f"Fetching Amazon data for {brand}... ({i+1}/{len(all_brands)})")
                    
                    data = get_amazon_keyword_volumes(
                        dataforseo_login, dataforseo_password, brand,
                        location_code, months_back
                    )
                    amazon_results.append(data)
                    
                    progress_bar.progress((i + 1) / len(all_brands))
                    
                    if i < len(all_brands) - 1:
                        time.sleep(1)  # Rate limiting
                
                status.empty()
                progress_bar.empty()
            
            # Process Amazon results
            if any(r['avg_volume'] > 0 for r in amazon_results):
                st.session_state.amazon_results = amazon_results
                
                df_amazon_avg = pd.DataFrame([{
                    'brand': r['brand'],
                    'avg_volume': r['avg_volume'],
                    'is_target': r['brand'] == target_brand
                } for r in amazon_results])
                
                total_volume = df_amazon_avg['avg_volume'].sum()
                df_amazon_avg['share_of_search'] = (df_amazon_avg['avg_volume'] / total_volume * 100).round(2)
                df_amazon_avg = df_amazon_avg.sort_values('avg_volume', ascending=False).reset_index(drop=True)
                
                # Monthly trends
                monthly_data = []
                for r in amazon_results:
                    for month, volume in r['monthly_volumes'].items():
                        monthly_data.append({
                            'brand': r['brand'],
                            'month': month,
                            'volume': volume
                        })
                
                df_amazon_monthly = pd.DataFrame(monthly_data)
                
                if not df_amazon_monthly.empty:
                    monthly_totals = df_amazon_monthly.groupby('month')['volume'].sum().reset_index()
                    monthly_totals.columns = ['month', 'total']
                    
                    df_amazon_monthly = df_amazon_monthly.merge(monthly_totals, on='month')
                    df_amazon_monthly['share_of_search'] = (df_amazon_monthly['volume'] / df_amazon_monthly['total'] * 100).round(2)
                
                # Display Amazon results
                st.success("✅ Amazon data collected!")
                
                # Key metrics
                target_row = df_amazon_avg[df_amazon_avg['is_target']].iloc[0]
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Amazon SoS", f"{target_row['share_of_search']:.2f}%")
                with col2:
                    st.metric("Search Volume", f"{target_row['avg_volume']:,}")
                with col3:
                    rank = (df_amazon_avg['avg_volume'] > target_row['avg_volume']).sum() + 1
                    st.metric("Market Rank", f"#{rank}")
                
                # Charts
                st.subheader("📈 Amazon Trends Over Time")
                st.info("ℹ️ Note: DataforSEO provides average volumes. Monthly trends shown use this average.")
                fig = create_sos_trend_chart(df_amazon_monthly, target_brand, "Amazon Share of Search Trends")
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                create_comparison_charts(df_amazon_avg, target_brand, "Amazon")
                
                # Data table
                with st.expander("📋 View Amazon Data Table"):
                    display_df = df_amazon_avg[['brand', 'avg_volume', 'share_of_search']].copy()
                    display_df.columns = ['Brand', 'Avg Monthly Volume', 'Share of Search (%)']
                    st.dataframe(display_df, use_container_width=True)
                    
                    csv = df_amazon_avg.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Download Amazon CSV",
                        csv,
                        f"amazon_sos_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv"
                    )
            else:
                st.error("❌ No Amazon data collected. Check your DataforSEO credentials.")
        
        tab_idx += 1
    
    # ==========================================
    # COMBINED SOS TAB
    # ==========================================
    
    if (st.session_state.google_results and st.session_state.amazon_results and 
        any(r['avg_volume'] > 0 for r in st.session_state.google_results) and
        any(r['avg_volume'] > 0 for r in st.session_state.amazon_results)):
        
        with tab_objects[tab_idx]:
            st.header("🌐 Combined Multi-Platform Share of Search")
            
            # Combine data
            combined_data = []
            
            for brand in all_brands:
                google_vol = next((r['avg_volume'] for r in st.session_state.google_results if r['brand'] == brand), 0)
                amazon_vol = next((r['avg_volume'] for r in st.session_state.amazon_results if r['brand'] == brand), 0)
                
                combined_data.append({
                    'brand': brand,
                    'google_volume': google_vol,
                    'amazon_volume': amazon_vol,
                    'total_volume': google_vol + amazon_vol,
                    'is_target': brand == target_brand
                })
            
            df_combined = pd.DataFrame(combined_data)
            
            total_combined = df_combined['total_volume'].sum()
            df_combined['combined_sos'] = (df_combined['total_volume'] / total_combined * 100).round(2)
            df_combined['google_sos'] = (df_combined['google_volume'] / df_combined['google_volume'].sum() * 100).round(2) if df_combined['google_volume'].sum() > 0 else 0
            df_combined['amazon_sos'] = (df_combined['amazon_volume'] / df_combined['amazon_volume'].sum() * 100).round(2) if df_combined['amazon_volume'].sum() > 0 else 0
            
            df_combined = df_combined.sort_values('total_volume', ascending=False).reset_index(drop=True)
            
            # Key metrics
            target_row = df_combined[df_combined['is_target']].iloc[0]
            
            st.subheader("🎯 Target Brand Performance")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Combined SoS", f"{target_row['combined_sos']:.2f}%")
            with col2:
                st.metric("Google SoS", f"{target_row['google_sos']:.2f}%")
            with col3:
                st.metric("Amazon SoS", f"{target_row['amazon_sos']:.2f}%")
            with col4:
                st.metric("Total Volume", f"{int(target_row['total_volume']):,}")
            
            # Stacked bar chart
            st.subheader("📊 Volume Breakdown by Platform")
            
            fig = go.Figure(data=[
                go.Bar(name='Google', x=df_combined['brand'], y=df_combined['google_volume'], marker_color='#4285F4'),
                go.Bar(name='Amazon', x=df_combined['brand'], y=df_combined['amazon_volume'], marker_color='#FF9900')
            ])
            
            fig.update_layout(
                barmode='stack',
                xaxis_title="Brand",
                yaxis_title="Search Volume",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Combined market share pie
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🥧 Combined Market Share")
                fig = px.pie(
                    df_combined, values='total_volume', names='brand',
                    hole=0.3
                )
                colors = ['#FF6B6B' if brand == target_brand else '#4ECDC4' 
                          for brand in df_combined['brand']]
                fig.update_traces(marker=dict(colors=colors))
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("📈 Platform Distribution")
                platform_data = pd.DataFrame({
                    'Platform': ['Google', 'Amazon'],
                    'Volume': [df_combined['google_volume'].sum(), df_combined['amazon_volume'].sum()]
                })
                fig = px.pie(
                    platform_data, values='Volume', names='Platform',
                    color='Platform',
                    color_discrete_map={'Google': '#4285F4', 'Amazon': '#FF9900'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Data table
            with st.expander("📋 View Combined Data Table"):
                display_df = df_combined[['brand', 'google_volume', 'amazon_volume', 'total_volume', 
                                         'google_sos', 'amazon_sos', 'combined_sos']].copy()
                display_df.columns = ['Brand', 'Google Vol', 'Amazon Vol', 'Total Vol', 
                                      'Google SoS (%)', 'Amazon SoS (%)', 'Combined SoS (%)']
                st.dataframe(display_df, use_container_width=True)
                
                csv = df_combined.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Download Combined CSV",
                    csv,
                    f"combined_sos_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv"
                )

else:
    # Initial instructions
    st.info("👈 Configure settings in the sidebar and click 'Run Analysis' to begin")
    
    with st.expander("📚 Setup Guide", expanded=True):
        st.markdown("""
        ## Getting Started
        
        This tool analyzes Share of Search across **Google** and **Amazon** search platforms.
        
        ### Step 1: Choose Platforms
        
        Select which platforms you want to analyze:
        - ✅ **Google Search** - Requires Google Ads API credentials
        - ✅ **Amazon Search** - Requires DataforSEO API credentials
        - ✅ **Both** - Get combined cross-platform analysis
        
        ### Step 2: Configure APIs
        
        #### Google Ads API
        1. Create account at [Google Ads API Center](https://developers.google.com/google-ads/api)
        2. Generate OAuth credentials and developer token
        3. Create `google-ads.yaml` file with your credentials
        4. Upload in sidebar
        
        #### DataforSEO API
        1. Sign up at [DataforSEO.com](https://dataforseo.com/)
        2. Add $20-50 credit (pay-as-you-go pricing)
        3. Get Login (email) and Password (API key) from dashboard
        4. Enter credentials in sidebar
        
        **Cost:** ~$0.10-0.50 per brand keyword on Amazon
        
        ### Step 3: Configure Analysis
        
        - Enter your target brand
        - Add competitor brands (one per line)
        - Select date range (3-12 months)
        - Choose location/marketplace settings
        
        ### Step 4: Run Analysis
        
        Click "Run Analysis" to fetch data. The app will:
        1. Query Google Ads API for Google search volumes
        2. Query DataforSEO API for Amazon search volumes
        3. Calculate Share of Search for each platform
        4. Generate combined multi-platform analysis
        
        ### What You Get
        
        **Three Tabs:**
        - 🔵 **Google SoS** - Google Search analysis with monthly trends
        - 🟠 **Amazon SoS** - Amazon Search analysis
        - 🌐 **Combined SoS** - Unified cross-platform view
        
        **Key Metrics:**
        - Share of Search percentages by platform
        - Market rankings
        - Monthly trend charts
        - Volume breakdowns
        - CSV exports
        
        ---
        
        ### Understanding Share of Search (SoS)
        
        **Share of Search** = Your brand's search volume ÷ Total category search volume × 100
        
        Research shows SoS correlates 80%+ with market share, making it a leading indicator of business performance.
        """)
