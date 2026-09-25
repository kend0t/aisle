import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="VAST", layout="wide", page_icon="👁️‍🗨️")
st.title("👁️‍🗨️ VAST")
st.markdown("#### Vision-based Aisle Spatial Tracker")

@st.cache_data
def load_and_clean_data(csv_path):
    sys_df = pd.read_csv(csv_path)
    
    id_mapping = {
        1: "Customer_A", 2: "Customer_B", 3: "Customer_C",
        7: "Customer_D", 10: "Customer_E", 
        12: "Customer_B", 14: "Customer_E", 15: "Customer_F",
        16: "Customer_F", 18: "Customer_F", 19: "Customer_G",
        20: "Customer_A", 21: "Customer_H", 23: "Customer_F",
        30: "Customer_H", 35: "Customer_E"
    }
    
    sys_df["true_customer_id"] = sys_df["customer_id"].map(id_mapping)
    sys_df = sys_df.dropna(subset=["true_customer_id"])
    
    base_columns = ["customer_id", "total_dwell", "path", "true_customer_id"]
    zone_columns = [col for col in sys_df.columns if col not in base_columns]
    
    agg_dict = {
        "total_dwell": "sum",
        "path": lambda x: " -> ".join(x.astype(str)),
        "customer_id": lambda x: ", ".join(map(str, sorted(set(x))))
    }
    
    for zone in zone_columns:
        agg_dict[zone] = "sum"
        
    cleaned_df = sys_df.groupby("true_customer_id").agg(agg_dict).reset_index()
    
    cleaned_df["true_customer_id"] = cleaned_df.apply(
        lambda row: f"{row['true_customer_id']} (ID {row['customer_id']})", axis=1
    )
    
    desired_zone_order = ["Aisle 1", "Aisle 2", "Aisle 3", "Aisle 4", "Aisle 5", "Aisle 6", "Cashier"]
    existing_zones = [z for z in desired_zone_order if z in cleaned_df.columns]
    
    final_columns = ["true_customer_id", "total_dwell", "path"] + existing_zones
    cleaned_df = cleaned_df[final_columns]
    
    return cleaned_df, existing_zones

st.markdown("<h3 style='text-align: center;'>Live Tracking Feed</h3>", unsafe_allow_html=True)
col_v1, col_v2, col_v3 = st.columns([1, 2, 1])

with col_v2:
    video_path = os.path.join("output", "web_output.mp4")
    try:
        with open(video_path, 'rb') as video_file:
            st.video(video_file.read())
    except FileNotFoundError:
        st.error(f"Video not found at {video_path}. Please run main.py first.")

st.divider()

csv_path = os.path.join("output", "system_output.csv")
try:
    df, existing_zones = load_and_clean_data(csv_path)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 KPI Dashboard", "📈 Dwell Time Charts", "📋 Customer Pathways", "🎯 System Accuracy"])
    
    with tab1:
        st.subheader("Store Performance Metrics")
        
        total_traffic = len(df)
        avg_dwell = df['total_dwell'].mean()
        
        conversion_rate = 0
        if "Cashier" in df.columns:
            buyers = len(df[df["Cashier"] > 0])
            conversion_rate = (buyers / total_traffic) * 100 if total_traffic > 0 else 0
            
        busiest_zone = "N/A"
        if existing_zones:
            shopping_zones = [z for z in existing_zones if z != "Cashier"]
            if shopping_zones:
                zone_sums = df[shopping_zones].sum()
                busiest_zone = zone_sums.idxmax()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Foot Traffic", f"{total_traffic} Shoppers", border=True)
        m2.metric("Average Dwell Time", f"{avg_dwell:.1f} sec", border=True)
        m3.metric("Checkout Conversion", f"{conversion_rate:.1f}%", border=True)
        m4.metric("Busiest Shopping Aisle", busiest_zone, border=True)
        
    with tab2:
        st.subheader("Dwell Time Analysis")
        chart_data = df.set_index('true_customer_id')
        
        st.write("**Total Time in Store per Customer**")
        st.bar_chart(chart_data['total_dwell'])
        
        if existing_zones:
            st.write("**Zone-by-Zone Breakdown (Stacked)**")
            zone_chart_data = chart_data[existing_zones]
            st.bar_chart(zone_chart_data)
            
    with tab3:
        st.subheader("Customer Data")
        st.dataframe(df, use_container_width=True)

    with tab4:
        st.subheader("Automated Tracking Accuracy vs. Ground Truth")
        try:
            eval_df = pd.read_csv("evaluation/evaluation_metrics.csv")
            
            mae = eval_df["absolute_error"].mean()
            overall_acc = eval_df["accuracy_percentage"].mean()
            
            e_col1, e_col2 = st.columns(2)
            e_col1.metric("Mean Absolute Error (MAE)", f"{mae:.2f} sec", border=True)
            e_col2.metric("Overall System Accuracy", f"{overall_acc:.1f}%", border=True)
            
            st.write("**Customer-Level Tracking Variance**")
            chart_data = eval_df.set_index("true_customer_id")[["gt_total_dwell", "sys_total_dwell"]]
            st.bar_chart(chart_data)
            
            st.write("**Detailed Evaluation Metrics**")
            st.dataframe(eval_df, use_container_width=True)
            
        except FileNotFoundError:
            st.error("Evaluation metrics not found. Please ensure 'evaluation_metrics.csv' is in the correct directory.")

except FileNotFoundError:
    st.error(f"Data not found at {csv_path}. Please run main.py first.")