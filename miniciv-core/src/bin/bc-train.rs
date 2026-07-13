// P1.5 BC训练: 从FlatMC数据训练6个softmax分类器
// 用法: cargo run --release --bin bc-train -- [data.csv] [weights.json]
// 默认: bc-training-data.csv → bc-weights.json
use std::collections::{HashMap, BTreeMap};
use std::io::Write;
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha12Rng;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let data_path = args.get(1).cloned().unwrap_or_else(|| "../experiments/v0.10-redwhite/bc-training-data.csv".to_string());
    let out_path = args.get(2).cloned().unwrap_or_else(|| "../experiments/v0.10-redwhite/bc-weights.json".to_string());

    // 读取CSV
    let content = std::fs::read_to_string(&data_path).expect("cannot read data file");
    let lines: Vec<&str> = content.lines().collect();
    if lines.len() < 2 { eprintln!("empty data"); return; }

    // 解析header找到各列索引
    let header: Vec<&str> = lines[0].split(',').collect();
    let col = |name: &str| -> usize { header.iter().position(|&h| h == name).unwrap() };
    let feat_start = col("my_support");
    // 标签列
    let label_cols = [col("act_research"), col("act_produce"), col("act_posture"), col("act_branch"), col("act_redeem"), col("act_expand")];

    // 收集数据
    let mut features: Vec<Vec<f64>> = Vec::new();
    let mut labels: Vec<[String; 6]> = Vec::new();
    for line in &lines[1..] {
        if line.is_empty() { continue; }
        let parts: Vec<&str> = line.split(',').collect();
        if parts.len() < feat_start + 25 { continue; }
        let feats: Vec<f64> = (feat_start..feat_start+25).map(|i| parts[i].parse::<f64>().unwrap_or(0.0)).collect();
        let labs: [String; 6] = [
            parts[label_cols[0]].to_string(), parts[label_cols[1]].to_string(),
            parts[label_cols[2]].to_string(), parts[label_cols[3]].to_string(),
            parts[label_cols[4]].to_string(), parts[label_cols[5]].to_string(),
        ];
        features.push(feats);
        labels.push(labs);
    }
    eprintln!("加载 {} 条训练数据", features.len());

    // 为每个动作轴训练独立softmax分类器
    let n_feats = 25;
    let learning_rate = 0.01;
    let epochs = 200;
    let mut rng = rand_chacha::ChaCha12Rng::seed_from_u64(42);

    let mut all_weights: BTreeMap<String, serde_json::Value> = BTreeMap::new();

    for (ax_idx, ax_name) in ["research","produce","posture","branch","redeem","expand"].iter().enumerate() {
        // 收集该轴的类别
        let mut class_set: Vec<String> = Vec::new();
        let mut class_to_idx: HashMap<String, usize> = HashMap::new();
        for lab in &labels {
            let c = &lab[ax_idx];
            if !class_to_idx.contains_key(c) {
                class_to_idx.insert(c.clone(), class_set.len());
                class_set.push(c.clone());
            }
        }
        let n_classes = class_set.len();
        eprintln!("  {}: {} classes ({:?})", ax_name, n_classes, &class_set[..3.min(n_classes)]);

        // 初始化权重矩阵 [n_classes × (n_feats+1)] (+1 for bias)
        let mut weights: Vec<Vec<f64>> = (0..n_classes).map(|_| {
            (0..=n_feats).map(|_| (rng.gen::<f64>() - 0.5) * 0.1).collect::<Vec<f64>>()
        }).collect();

        // SGD训练
        for epoch in 0..epochs {
            let mut total_loss = 0.0f64;
            let mut correct = 0u32;
            let mut perm: Vec<usize> = (0..features.len()).collect();
            // shuffle
            for i in (1..perm.len()).rev() { let j = rng.gen_range(0..=i); perm.swap(i, j); }

            for &idx in &perm {
                let x = &features[idx];
                let true_class = class_to_idx[&labels[idx][ax_idx]];

                // forward: compute scores and softmax
                let mut scores: Vec<f64> = weights.iter().map(|w| {
                    let mut s = w[n_feats]; // bias
                    for i in 0..n_feats { s += w[i] * x[i]; }
                    s
                }).collect();

                // softmax with numerical stability
                let max_s = scores.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
                let mut sum_exp = 0.0;
                for s in &mut scores { *s = (*s - max_s).exp(); sum_exp += *s; }
                for s in &mut scores { *s /= sum_exp; }

                // loss
                total_loss -= scores[true_class].ln();
                if scores.iter().enumerate().max_by(|a,b| a.1.partial_cmp(b.1).unwrap()).unwrap().0 == true_class {
                    correct += 1;
                }

                // backward: gradient and update
                for c in 0..n_classes {
                    let grad_mult = if c == true_class { scores[c] - 1.0 } else { scores[c] };
                    for i in 0..n_feats { weights[c][i] -= learning_rate * grad_mult * x[i]; }
                    weights[c][n_feats] -= learning_rate * grad_mult; // bias
                }
            }

            if epoch % 50 == 0 || epoch == epochs - 1 {
                let acc = correct as f64 / features.len() as f64 * 100.0;
                eprintln!("    {} epoch {}: loss={:.3} acc={:.1}%", ax_name, epoch, total_loss / features.len() as f64, acc);
            }
        }

        // 保存权重
        let mut wmap: BTreeMap<String, serde_json::Value> = BTreeMap::new();
        wmap.insert("classes".to_string(), serde_json::json!(class_set));
        wmap.insert("weights".to_string(), serde_json::json!(weights));
        all_weights.insert(ax_name.to_string(), serde_json::json!(wmap));
    }

    let json = serde_json::to_string_pretty(&all_weights).unwrap();
    std::fs::write(&out_path, &json).unwrap();
    eprintln!("权重已保存 → {}", out_path);
}
