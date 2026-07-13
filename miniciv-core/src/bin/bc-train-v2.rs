// BC V2训练: 监督学习, 复用V2b NN架构, 从自对弈数据训练
// 用法: cargo run --release --bin bc-train-v2 -- [data.csv] [weights_out.json]
use std::collections::{HashMap, BTreeMap};
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha12Rng;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let data_path = args.get(1).cloned().unwrap_or_else(|| "../experiments/v0.10-redwhite/bc-selfplay-data.csv".to_string());
    let out_path = args.get(2).cloned().unwrap_or_else(|| "../experiments/v0.10-redwhite/bc-v2-weights.json".to_string());

    // 读取数据
    let content = std::fs::read_to_string(&data_path).expect("no data");
    let lines: Vec<&str> = content.lines().collect();
    if lines.len() < 2 { eprintln!("empty"); return; }

    let header: Vec<&str> = lines[0].split(',').collect();
    let col = |n:&str| header.iter().position(|&h|h==n).unwrap();
    let feat_start = col("my_support");
    let lbl_cols = [col("act_research"),col("act_produce"),col("act_posture"),col("act_branch"),col("act_redeem"),col("act_expand")];

    // 收集数据
    let mut features: Vec<Vec<f64>> = Vec::new();
    let mut labels: Vec<[String;6]> = Vec::new();
    for line in &lines[1..] {
        if line.is_empty() { continue; }
        let p: Vec<&str> = line.split(',').collect();
        if p.len() < feat_start+25 { continue; }
        let fs: Vec<f64> = (feat_start..feat_start+25).map(|i| p[i].parse::<f64>().unwrap_or(0.0)).collect();
        let ls: [String;6] = [p[lbl_cols[0]].into(),p[lbl_cols[1]].into(),p[lbl_cols[2]].into(),p[lbl_cols[3]].into(),p[lbl_cols[4]].into(),p[lbl_cols[5]].into()];
        features.push(fs); labels.push(ls);
    }
    eprintln!("{} 条训练数据", features.len());

    // 初始化NN参数(复用V2b架构)
    let n_in=25; let n_h1=32; let n_h2=16;
    let mut rng = ChaCha12Rng::seed_from_u64(42);
    let rand_mat = |r:usize,c:usize| -> Vec<Vec<f64>> { let s=(2.0/c as f64).sqrt(); (0..r).map(|_|(0..c).map(|_|rng.gen_range(-s..s)).collect()).collect() };
    let mut w1=rand_mat(n_h1,n_in); let mut b1=vec![0.0f64;n_h1];
    let mut w2=rand_mat(n_h2,n_h1); let mut b2=vec![0.0f64;n_h2];

    // 6个输出头(从数据统计类别)
    let axes = ["research","produce","posture","branch","redeem","expand"];
    let mut head_classes: Vec<Vec<String>> = Vec::new();
    let mut head_w: Vec<Vec<Vec<f64>>> = Vec::new();
    let mut head_b: Vec<Vec<f64>> = Vec::new();
    for ax in 0..6 {
        let mut classes: Vec<String> = Vec::new();
        let mut c2i: HashMap<String,usize> = HashMap::new();
        for l in &labels {
            let c = &l[ax];
            if !c2i.contains_key(c) { c2i.insert(c.clone(),classes.len()); classes.push(c.clone()); }
        }
        let nc = classes.len();
        head_classes.push(classes);
        head_w.push(rand_mat(nc,n_h2));
        head_b.push(vec![0.0f64;nc]);
    }
    eprintln!("架构: 25→32→16→{:?}类", head_classes.iter().map(|c|c.len()).collect::<Vec<_>>());

    // Adam训练
    let lr=0.001; let b1a=0.9; let b2a=0.999; let eps=1e-8; let epochs=300; let batch=64;
    let n = features.len();
    let mut adam = vec![vec![vec![0.0f64;0];0];8]; // 简化: 用固定lr

    for ep in 0..epochs {
        let mut loss_sum=0.0f64; let mut correct=0u32; let mut total=0u32;
        // shuffle batch indices
        let mut idxs: Vec<usize> = (0..n).collect();
        for i in (1..idxs.len()).rev() { let j=rng.gen_range(0..=i); idxs.swap(i,j); }

        for batch_start in (0..n).step_by(batch) {
            let batch_end = (batch_start+batch).min(n);
            // 累积梯度
            let mut gw1=vec![vec![0.0;n_in];n_h1]; let mut gb1=vec![0.0;n_h1];
            let mut gw2=vec![vec![0.0;n_h1];n_h2]; let mut gb2=vec![0.0;n_h2];
            let mut ghw: Vec<Vec<Vec<f64>>> = head_w.iter().map(|hw| vec![vec![0.0;n_h2];hw.len()]).collect();
            let mut ghb: Vec<Vec<f64>> = head_b.iter().map(|hb| vec![0.0;hb.len()]).collect();

            for &bi in &idxs[batch_start..batch_end] {
                let x=&features[bi];
                // forward
                let mut h1=vec![0.0;n_h1]; for i in 0..n_h1{let mut s=b1[i];for j in 0..n_in{s+=w1[i][j]*x[j];}h1[i]=if s>0.0{s}else{0.0};}
                let mut h2=vec![0.0;n_h2]; for i in 0..n_h2{let mut s=b2[i];for j in 0..n_h1{s+=w2[i][j]*h1[j];}h2[i]=if s>0.0{s}else{0.0};}

                // 每个头: softmax loss
                for ax in 0..6 {
                    let hw=&head_w[ax]; let hb=&head_b[ax]; let nc=head_classes[ax].len();
                    let true_c = head_classes[ax].iter().position(|c|c==&labels[bi][ax]).unwrap_or(0);
                    // forward head
                    let mut scores=vec![0.0;nc]; for i in 0..nc{let mut s=hb[i];for j in 0..n_h2{s+=hw[i][j]*h2[j];}scores[i]=s;}
                    let max_s=scores.iter().cloned().fold(f64::NEG_INFINITY,f64::max);
                    let mut sum_exp=0.0; for s in &mut scores{*s=(*s-max_s).exp();sum_exp+=*s;} for s in &mut scores{*s/=sum_exp;}
                    loss_sum -= scores[true_c].ln();
                    if scores.iter().enumerate().max_by(|a,b|a.1.partial_cmp(b.1).unwrap()).unwrap().0==true_c{correct+=1;}
                    total+=1;

                    // backward head: dL/dscore, dL/dhw, dL/dhb, dL/dh2
                    let mut dscores=vec![0.0;nc]; dscores[true_c]=scores[true_c]-1.0;
                    for i in 0..nc{ if dscores[i].abs()>1e-9{
                        for j in 0..n_h2{ ghw[ax][i][j] += dscores[i]*h2[j]; }
                        ghb[ax][i] += dscores[i];
                    }}
                }
            }

            // SGD update (简化版, 不加Adam了, 直接SGD)
            let scale = lr / (batch_end-batch_start) as f64;
            for i in 0..n_h1{for j in 0..n_in{w1[i][j]-=scale*gw1[i][j];}b1[i]-=scale*gb1[i];}
            for i in 0..n_h2{for j in 0..n_h1{w2[i][j]-=scale*gw2[i][j];}b2[i]-=scale*gb2[i];}
            for ax in 0..6{for i in 0..head_w[ax].len(){for j in 0..n_h2{head_w[ax][i][j]-=scale*ghw[ax][i][j];}head_b[ax][i]-=scale*ghb[ax][i];}}
        }

        if ep%50==0||ep==epochs-1{
            eprintln!("epoch {}: loss={:.3} acc={:.1}%",ep,loss_sum/total as f64,correct as f64/total as f64*100.0);
        }
    }

    // 保存(兼容train-evo-v2格式)
    let mut flat_w: Vec<f64> = Vec::new();
    for r in &w1{for &v in r{flat_w.push(v);}} for &v in &b1{flat_w.push(v);}
    for r in &w2{for &v in r{flat_w.push(v);}} for &v in &b2{flat_w.push(v);}
    for ax in 0..6{for r in &head_w[ax]{for &v in r{flat_w.push(v);}}for &v in &head_b[ax]{flat_w.push(v);}}
    let head_sizes: Vec<usize> = head_classes.iter().map(|c|c.len()).collect();
    let action_map: Vec<Vec<String>> = head_classes.clone();
    let output = serde_json::json!({"weights":flat_w,"head_sizes":head_sizes,"action_map":action_map});
    std::fs::write(&out_path, serde_json::to_string_pretty(&output).unwrap()).unwrap();
    eprintln!("BC-V2训练完成 → {}", out_path);
}
