import pandas as pd
import os

def calculate_metrics(system_csv, gt_csv, output_path):
    # 1. Load Data
    ground_truth_df = pd.read_csv(gt_csv)
    ground_truth_df = ground_truth_df.rename(columns={
        "customer_id": "true_customer_id", 
        "total_dwell": "gt_total_dwell"
    })

    sys_df = pd.read_csv(system_csv)
    
    # 2. Identity Mapping (Fragmeted IDs -> True Customers)
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

    # 3. Aggregate Dwell Times
    system_cleaned_df = sys_df.groupby("true_customer_id").agg(
        sys_total_dwell=("total_dwell", "sum")
    ).reset_index()

    # 4. Merge and Calculate
    evaluation_df = pd.merge(ground_truth_df, system_cleaned_df, on="true_customer_id", how="inner")
    
    evaluation_df["variance_seconds"] = evaluation_df["sys_total_dwell"] - evaluation_df["gt_total_dwell"]
    evaluation_df["absolute_error"] = evaluation_df["variance_seconds"].abs()
    
    # Accuracy Formula
    evaluation_df["accuracy_percentage"] = 100 - ((evaluation_df["absolute_error"] / evaluation_df["gt_total_dwell"]) * 100)
    evaluation_df["accuracy_percentage"] = evaluation_df["accuracy_percentage"].clip(lower=0, upper=100)

    # 5. Export and Summarize
    evaluation_df.to_csv(output_path, index=False)
    
    mae = evaluation_df["absolute_error"].mean()
    overall_accuracy = evaluation_df["accuracy_percentage"].mean()

    print("="*40)
    print(f"Mean Absolute Error (MAE): {mae:.2f} seconds")
    print(f"Overall Dwell Accuracy:    {overall_accuracy:.2f}%")
    print("="*40)