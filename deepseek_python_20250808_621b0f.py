import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime
from fuzzywuzzy import fuzz, process
from io import BytesIO
import base64

# Configure Streamlit page
st.set_page_config(
    page_title="Reco-Buddy",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply dark theme with custom styling
def apply_dark_theme():
    dark_theme = """
    <style>
    :root {
        --primary: #1e2130;
        --secondary: #2a2f4f;
        --accent: #6c5ce7;
        --text: #f1f1f1;
        --success: #00b894;
        --warning: #fdcb6e;
        --danger: #ff7675;
    }
    
    body {
        background-color: var(--primary);
        color: var(--text);
    }
    
    .stApp {
        background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
        color: var(--text);
    }
    
    .stTextInput>div>div>input, .stNumberInput>div>div>input {
        background-color: rgba(30, 33, 48, 0.8);
        color: var(--text);
        border: 1px solid var(--accent);
    }
    
    .stDataFrame {
        background-color: rgba(30, 33, 48, 0.8);
    }
    
    .stButton>button {
        background-color: var(--accent);
        color: white;
        border-radius: 8px;
        border: none;
        padding: 8px 16px;
        font-weight: bold;
        transition: all 0.3s;
    }
    
    .stButton>button:hover {
        background-color: #5d4de0;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    .header {
        background: rgba(30, 33, 48, 0.8);
        padding: 1.5rem;
        border-radius: 15px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 16px rgba(0,0,0,0.2);
    }
    
    .card {
        background: rgba(42, 47, 79, 0.8);
        border-radius: 15px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        border: 1px solid rgba(108, 92, 231, 0.3);
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #f1f1f1;
    }
    
    .stAlert {
        border-radius: 10px;
    }
    
    .success-box {
        background-color: rgba(0, 184, 148, 0.2);
        border-left: 5px solid var(--success);
    }
    
    .warning-box {
        background-color: rgba(253, 203, 110, 0.2);
        border-left: 5px solid var(--warning);
    }
    
    .danger-box {
        background-color: rgba(255, 118, 117, 0.2);
        border-left: 5px solid var(--danger);
    }
    
    .stSelectbox>div>div>div {
        background-color: rgba(30, 33, 48, 0.8);
        color: var(--text);
    }
    </style>
    """
    st.markdown(dark_theme, unsafe_allow_html=True)

apply_dark_theme()

# Reconciliation Engine
class RecoBuddy:
    def __init__(self):
        self.ais_data = None
        self.cg_data = None
        self.mapped_data = None
        self.stock_totals = None
        self.unmapped_ais = None
        self.unmapped_cg = None
    
    def load_data(self, ais_df, cg_df):
        """Load and preprocess AIS and CG data"""
        self.ais_data = ais_df.copy()
        self.cg_data = cg_df.copy()
        
        # Preprocess stock names
        self.ais_data['Stock Name Clean'] = self.ais_data['Stock Name (AIS)'].str.upper().str.strip()
        self.cg_data['Stock Name Clean'] = self.cg_data['Stock Name (CG)'].str.upper().str.strip()
        
        # Convert dates to datetime
        date_cols_ais = ['Sale Date (AIS)', 'Purchase Date (AIS)']
        date_cols_cg = ['Sale Date (CG)', 'Purchase Date (CG)']
        
        for col in date_cols_ais:
            if col in self.ais_data.columns:
                self.ais_data[col] = pd.to_datetime(self.ais_data[col], errors='coerce')
        
        for col in date_cols_cg:
            if col in self.cg_data.columns:
                self.cg_data[col] = pd.to_datetime(self.cg_data[col], errors='coerce')
        
        # Convert quantities and values to numeric
        num_cols = ['Quantity (AIS)', 'Quantity (CG)', 'Sales Value (AIS)', 
                   'Sales Value (CG)', 'Purchase Value (AIS)', 'Purchase Value (CG)']
        
        for col in num_cols:
            if col in self.ais_data.columns:
                self.ais_data[col] = pd.to_numeric(self.ais_data[col], errors='coerce')
            if col in self.cg_data.columns:
                self.cg_data[col] = pd.to_numeric(self.cg_data[col], errors='coerce')
        
        # Create unique IDs for matching
        self.ais_data['ID'] = range(1, len(self.ais_data) + 1
        self.cg_data['ID'] = range(1, len(self.cg_data) + 1)
    
    def fuzzy_match_stocks(self, name1, name2):
        """Intelligent fuzzy matching for stock names"""
        # Exact match
        if name1 == name2:
            return 100
        
        # Common substring match (at least 5 consecutive characters)
        if len(name1) >= 5 and len(name2) >= 5:
            for i in range(len(name1) - 4):
                substring = name1[i:i+5]
                if substring in name2:
                    return 90
        
        # Common abbreviations
        abbreviations = {
            "RELIANCE": ["RIL", "RELIANCE IND", "RELIANCE INDUSTRIES"],
            "MAHARASHTRA BANK": ["MAHABANK", "BANK OF MAHARASHTRA"],
            "HDFC BANK": ["HDFCBANK"],
            "LIC": ["LIFE INSURANCE CORP"]
        }
        
        for key, values in abbreviations.items():
            if name1 == key and name2 in values:
                return 95
            if name2 == key and name1 in values:
                return 95
        
        # Fuzzy matching
        return fuzz.token_set_ratio(name1, name2)
    
    def match_records(self):
        """Intelligent matching logic with multiple levels"""
        # Prepare data
        ais_df = self.ais_data.copy()
        cg_df = self.cg_data.copy()
        
        # Add match columns
        ais_df['Match ID'] = None
        ais_df['Match Type'] = None
        cg_df['Match ID'] = None
        cg_df['Match Type'] = None
        
        # Create a copy for unmatched records
        unmatched_ais = ais_df.copy()
        unmatched_cg = cg_df.copy()
        
        # Results storage
        matches = []
        match_id = 1
        
        # Level 1: Exact match on name, quantity, and sale date (within 1 day)
        for _, ais_row in unmatched_ais.iterrows():
            if pd.isna(ais_row['Sale Date (AIS)']):
                continue
                
            mask = (
                (unmatched_cg['Stock Name Clean'] == ais_row['Stock Name Clean']) &
                (unmatched_cg['Quantity (CG)'] == ais_row['Quantity (AIS)']) &
                (abs(unmatched_cg['Sale Date (CG)'] - ais_row['Sale Date (AIS)']) <= pd.Timedelta(days=1))
            )
            
            matches_found = unmatched_cg[mask]
            
            if not matches_found.empty:
                cg_row = matches_found.iloc[0]
                
                # Create match record
                match_record = {
                    'Match ID': match_id,
                    'Match Type': 'Level 1 (Exact Name, Qty, Date)',
                    'Stock Name (AIS)': ais_row['Stock Name (AIS)'],
                    'Stock Name (CG)': cg_row['Stock Name (CG)'],
                    'Quantity (AIS)': ais_row['Quantity (AIS)'],
                    'Quantity (CG)': cg_row['Quantity (CG)'],
                    'Sales Value (AIS)': ais_row['Sales Value (AIS)'],
                    'Sales Value (CG)': cg_row['Sales Value (CG)'],
                    'Sale Date (AIS)': ais_row['Sale Date (AIS)'],
                    'Sale Date (CG)': cg_row['Sale Date (CG)'],
                    'Purchase Value (AIS)': ais_row.get('Purchase Value (AIS)', None),
                    'Purchase Value (CG)': cg_row.get('Purchase Value (CG)', None),
                    'Purchase Date (AIS)': ais_row.get('Purchase Date (AIS)', None),
                    'Purchase Date (CG)': cg_row.get('Purchase Date (CG)', None)
                }
                matches.append(match_record)
                
                # Update dataframes
                unmatched_ais = unmatched_ais[unmatched_ais['ID'] != ais_row['ID']]
                unmatched_cg = unmatched_cg[unmatched_cg['ID'] != cg_row['ID']]
                match_id += 1
        
        # Level 2: Exact name and quantity (ignore date)
        for _, ais_row in unmatched_ais.iterrows():
            mask = (
                (unmatched_cg['Stock Name Clean'] == ais_row['Stock Name Clean']) &
                (unmatched_cg['Quantity (CG)'] == ais_row['Quantity (AIS)'])
            )
            
            matches_found = unmatched_cg[mask]
            
            if not matches_found.empty:
                cg_row = matches_found.iloc[0]
                
                match_record = {
                    'Match ID': match_id,
                    'Match Type': 'Level 2 (Exact Name, Qty)',
                    'Stock Name (AIS)': ais_row['Stock Name (AIS)'],
                    'Stock Name (CG)': cg_row['Stock Name (CG)'],
                    'Quantity (AIS)': ais_row['Quantity (AIS)'],
                    'Quantity (CG)': cg_row['Quantity (CG)'],
                    'Sales Value (AIS)': ais_row['Sales Value (AIS)'],
                    'Sales Value (CG)': cg_row['Sales Value (CG)'],
                    'Sale Date (AIS)': ais_row['Sale Date (AIS)'],
                    'Sale Date (CG)': cg_row['Sale Date (CG)'],
                    'Purchase Value (AIS)': ais_row.get('Purchase Value (AIS)', None),
                    'Purchase Value (CG)': cg_row.get('Purchase Value (CG)', None),
                    'Purchase Date (AIS)': ais_row.get('Purchase Date (AIS)', None),
                    'Purchase Date (CG)': cg_row.get('Purchase Date (CG)', None)
                }
                matches.append(match_record)
                
                unmatched_ais = unmatched_ais[unmatched_ais['ID'] != ais_row['ID']]
                unmatched_cg = unmatched_cg[unmatched_cg['ID'] != cg_row['ID']]
                match_id += 1
        
        # Level 3: Fuzzy name match with quantity match
        for _, ais_row in unmatched_ais.iterrows():
            # Find best fuzzy match
            best_match = None
            best_score = 0
            
            for _, cg_row in unmatched_cg.iterrows():
                score = self.fuzzy_match_stocks(
                    ais_row['Stock Name Clean'], 
                    cg_row['Stock Name Clean']
                )
                
                if score > 80 and cg_row['Quantity (CG)'] == ais_row['Quantity (AIS)'] and score > best_score:
                    best_score = score
                    best_match = cg_row
            
            if best_match is not None:
                match_record = {
                    'Match ID': match_id,
                    'Match Type': f'Level 3 (Fuzzy Name: {best_score}%, Qty)',
                    'Stock Name (AIS)': ais_row['Stock Name (AIS)'],
                    'Stock Name (CG)': best_match['Stock Name (CG)'],
                    'Quantity (AIS)': ais_row['Quantity (AIS)'],
                    'Quantity (CG)': best_match['Quantity (CG)'],
                    'Sales Value (AIS)': ais_row['Sales Value (AIS)'],
                    'Sales Value (CG)': best_match['Sales Value (CG)'],
                    'Sale Date (AIS)': ais_row['Sale Date (AIS)'],
                    'Sale Date (CG)': best_match['Sale Date (CG)'],
                    'Purchase Value (AIS)': ais_row.get('Purchase Value (AIS)', None),
                    'Purchase Value (CG)': best_match.get('Purchase Value (CG)', None),
                    'Purchase Date (AIS)': ais_row.get('Purchase Date (AIS)', None),
                    'Purchase Date (CG)': best_match.get('Purchase Date (CG)', None)
                }
                matches.append(match_record)
                
                unmatched_ais = unmatched_ais[unmatched_ais['ID'] != ais_row['ID']]
                unmatched_cg = unmatched_cg[unmatched_cg['ID'] != best_match['ID']]
                match_id += 1
        
        # Level 4: Aggregate quantity matching for same stock
        # Group unmatched records by stock name
        ais_groups = unmatched_ais.groupby('Stock Name Clean')
        cg_groups = unmatched_cg.groupby('Stock Name Clean')
        
        for stock_name, ais_group in ais_groups:
            # Find matching CG stock group using fuzzy matching
            cg_match_name = None
            best_score = 0
            
            for cg_stock in cg_groups.groups.keys():
                score = self.fuzzy_match_stocks(stock_name, cg_stock)
                if score > 85 and score > best_score:
                    best_score = score
                    cg_match_name = cg_stock
            
            if cg_match_name:
                cg_group = cg_groups.get_group(cg_match_name)
                
                # Check if total quantities match
                ais_total_qty = ais_group['Quantity (AIS)'].sum()
                cg_total_qty = cg_group['Quantity (CG)'].sum()
                
                if ais_total_qty == cg_total_qty:
                    # Create a single match record for the aggregated values
                    match_record = {
                        'Match ID': match_id,
                        'Match Type': f'Level 4 (Aggregate: {best_score}%)',
                        'Stock Name (AIS)': ', '.join(ais_group['Stock Name (AIS)'].unique()),
                        'Stock Name (CG)': ', '.join(cg_group['Stock Name (CG)'].unique()),
                        'Quantity (AIS)': ais_total_qty,
                        'Quantity (CG)': cg_total_qty,
                        'Sales Value (AIS)': ais_group['Sales Value (AIS)'].sum(),
                        'Sales Value (CG)': cg_group['Sales Value (CG)'].sum(),
                        'Sale Date (AIS)': "Multiple",
                        'Sale Date (CG)': "Multiple",
                        'Purchase Value (AIS)': ais_group.get('Purchase Value (AIS)', 0).sum(),
                        'Purchase Value (CG)': cg_group.get('Purchase Value (CG)', 0).sum(),
                        'Purchase Date (AIS)': "Multiple",
                        'Purchase Date (CG)': "Multiple"
                    }
                    matches.append(match_record)
                    
                    # Remove matched records
                    unmatched_ais = unmatched_ais[~unmatched_ais['ID'].isin(ais_group['ID'])]
                    unmatched_cg = unmatched_cg[~unmatched_cg['ID'].isin(cg_group['ID'])]
                    match_id += 1
        
        # Create final matched dataframe
        if matches:
            self.mapped_data = pd.DataFrame(matches)
            
            # Calculate sales difference
            self.mapped_data['Sales Difference'] = (
                self.mapped_data['Sales Value (AIS)'] - 
                self.mapped_data['Sales Value (CG)']
            )
        else:
            self.mapped_data = pd.DataFrame()
        
        # Store unmatched records
        self.unmapped_ais = unmatched_ais.drop(columns=['Stock Name Clean', 'ID'])
        self.unmapped_cg = unmatched_cg.drop(columns=['Stock Name Clean', 'ID'])
        
        # Create stock-wise totals
        self.create_stock_totals()
    
    def create_stock_totals(self):
        """Create stock-wise totals for secondary report"""
        if self.mapped_data is None or self.mapped_data.empty:
            self.stock_totals = pd.DataFrame()
            return
        
        # Group by stock name
        stock_groups = self.mapped_data.groupby('Stock Name (AIS)')
        
        stock_data = []
        
        for stock, group in stock_groups:
            stock_data.append({
                'Stock Name': stock,
                'AIS Quantity': group['Quantity (AIS)'].sum(),
                'CG Quantity': group['Quantity (CG)'].sum(),
                'Quantity Difference': group['Quantity (AIS)'].sum() - group['Quantity (CG)'].sum(),
                'AIS Sales': group['Sales Value (AIS)'].sum(),
                'CG Sales': group['Sales Value (CG)'].sum(),
                'Sales Difference': group['Sales Value (AIS)'].sum() - group['Sales Value (CG)'].sum(),
                'Match Types': ', '.join(group['Match Type'].unique())
            })
        
        self.stock_totals = pd.DataFrame(stock_data)

# Helper function for download button
def get_table_download_link(df, filename):
    """Generates a link allowing the data in a given panda dataframe to be downloaded"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()  # some strings <-> bytes conversions necessary here
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}.csv">Download {filename}</a>'
    return href

# Streamlit App
def main():
    # Create sidebar
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3063/3063792.png", width=80)
        st.title("Reco-Buddy")
        st.markdown("**Intelligent Reconciliation Tool for AIS and Broker PNL**")
        
        st.markdown("---")
        st.markdown("### How to Use:")
        st.markdown("1. Paste your AIS data in the left table")
        st.markdown("2. Paste your Broker PNL data in the right table")
        st.markdown("3. Click 'Reconcile Data'")
        st.markdown("4. View and download reconciliation reports")
        
        st.markdown("---")
        st.markdown("### Tips:")
        st.markdown("- Use consistent stock naming for best results")
        st.markdown("- The tool handles splits and aggregates automatically")
        st.markdown("- Fuzzy matching works for common abbreviations")
        
        st.markdown("---")
        st.markdown("Created with ❤️ by Financial Tech Solutions")
    
    # Header
    st.markdown('<div class="header">', unsafe_allow_html=True)
    st.title("🔍 Reco-Buddy: AIS and Broker PNL Reconciliation")
    st.markdown("Intelligent reconciliation tool with fuzzy matching and quantity aggregation")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Initialize session state
    if 'reconciler' not in st.session_state:
        st.session_state.reconciler = RecoBuddy()
    
    # Create two columns for data input
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("AIS Data Input")
        st.info("Paste your AIS data here with the following columns:")
        st.markdown("- Stock Name (AIS)")
        st.markdown("- Quantity (AIS)")
        st.markdown("- Sales Value (AIS)")
        st.markdown("- Sale Date (AIS)")
        st.markdown("- Purchase Value (AIS) [Optional]")
        st.markdown("- Purchase Date (AIS) [Optional]")
        
        ais_data = st.data_editor(
            pd.DataFrame(columns=[
                'Stock Name (AIS)', 'Quantity (AIS)', 'Sales Value (AIS)', 
                'Sale Date (AIS)', 'Purchase Value (AIS)', 'Purchase Date (AIS)'
            ]),
            num_rows="dynamic",
            height=300,
            use_container_width=True
        )
    
    with col2:
        st.subheader("Broker PNL (CG) Data Input")
        st.info("Paste your Broker PNL data here with the following columns:")
        st.markdown("- Stock Name (CG)")
        st.markdown("- Quantity (CG)")
        st.markdown("- Sales Value (CG)")
        st.markdown("- Sale Date (CG)")
        st.markdown("- Purchase Value (CG) [Optional]")
        st.markdown("- Purchase Date (CG) [Optional]")
        
        cg_data = st.data_editor(
            pd.DataFrame(columns=[
                'Stock Name (CG)', 'Quantity (CG)', 'Sales Value (CG)', 
                'Sale Date (CG)', 'Purchase Value (CG)', 'Purchase Date (CG)'
            ]),
            num_rows="dynamic",
            height=300,
            use_container_width=True
        )
    
    # Reconciliation button
    if st.button("🚀 Reconcile Data", use_container_width=True):
        if not ais_data.empty and not cg_data.empty:
            with st.spinner("Reconciling data with intelligent mapping..."):
                st.session_state.reconciler.load_data(ais_data, cg_data)
                st.session_state.reconciler.match_records()
            st.success("Reconciliation completed successfully!")
        else:
            st.error("Please provide data in both tables before reconciling")
    
    # Show reconciliation results
    if st.session_state.reconciler.mapped_data is not None:
        if not st.session_state.reconciler.mapped_data.empty:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📊 Primary Reconciliation Report")
            st.dataframe(st.session_state.reconciler.mapped_data, use_container_width=True)
            
            # Download button for primary report
            st.markdown(get_table_download_link(
                st.session_state.reconciler.mapped_data, 
                "Primary_Reconciliation_Report"
            ), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Secondary report (stock totals)
            if not st.session_state.reconciler.stock_totals.empty:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.subheader("📈 Stock-wise Totals Report")
                st.dataframe(st.session_state.reconciler.stock_totals, use_container_width=True)
                
                # Download button for secondary report
                st.markdown(get_table_download_link(
                    st.session_state.reconciler.stock_totals, 
                    "Stock_Totals_Report"
                ), unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Show unmatched records
        col_unmapped1, col_unmapped2 = st.columns(2)
        
        with col_unmapped1:
            if not st.session_state.reconciler.unmapped_ais.empty:
                st.markdown('<div class="card warning-box">', unsafe_allow_html=True)
                st.subheader("⚠️ Unmatched AIS Records")
                st.dataframe(st.session_state.reconciler.unmapped_ais, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
        
        with col_unmapped2:
            if not st.session_state.reconciler.unmapped_cg.empty:
                st.markdown('<div class="card warning-box">', unsafe_allow_html=True)
                st.subheader("⚠️ Unmatched Broker Records")
                st.dataframe(st.session_state.reconciler.unmapped_cg, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Reconciliation summary
        if not st.session_state.reconciler.mapped_data.empty:
            total_matches = len(st.session_state.reconciler.mapped_data)
            unmatched_ais = len(st.session_state.reconciler.unmapped_ais)
            unmatched_cg = len(st.session_state.reconciler.unmapped_cg)
            
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("📝 Reconciliation Summary")
            
            col_sum1, col_sum2, col_sum3 = st.columns(3)
            
            with col_sum1:
                st.metric("Total Matched Records", total_matches)
            
            with col_sum2:
                st.metric("Unmatched AIS Records", unmatched_ais)
            
            with col_sum3:
                st.metric("Unmatched Broker Records", unmatched_cg)
            
            # Match type distribution
            if 'Match Type' in st.session_state.reconciler.mapped_data:
                match_counts = st.session_state.reconciler.mapped_data['Match Type'].value_counts()
                st.bar_chart(match_counts)
            
            st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()