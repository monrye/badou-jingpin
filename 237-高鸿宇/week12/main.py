# -*- coding: utf-8 -*-
import torch
import os
import random
import os
import numpy as np
import logging
from config import opt
from model import TorchModel
from evaluate import Evaluator
from loader import load_data
from peft import get_peft_model, LoraConfig, TaskType

logging.basicConfig(level = logging.INFO,format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

"""
模型训练主程序
"""

def main(opt):
    #创建保存模型的目录
    if not os.path.isdir(opt.model_path):
        os.mkdir(opt.model_path)
    #加载训练数据
    train_data = load_data(opt, True)
    #加载模型
    model = TorchModel(opt)

    peft_config = LoraConfig(task_type=TaskType.SEQ_CLS, inference_mode=False,
                             r=8, lora_alpha=32, lora_dropout=0.1, target_modules=["query", "key", "value"])
    
    model = get_peft_model(model, peft_config)

    # 标识是否使用gpu
    cuda_flag = torch.cuda.is_available()
    if cuda_flag:
        logger.info("gpu可以使用,迁移模型至gpu")
        model = model.cuda()
    #加载优化器
    optimizer = torch.optim.Adam(model.parameters(), lr=opt.lr)
    #加载效果测试类
    evaluator = Evaluator(opt, model, logger)
    #训练
    for epoch in range(opt.epoch):
        epoch += 1
        model.train()
        logger.info("epoch %d begin" % epoch)
        train_loss = []
        for index, batch_data in enumerate(train_data):
            optimizer.zero_grad()
            if cuda_flag:
                batch_data = [d.cuda() for d in batch_data]
            input_id, labels = batch_data   #输入变化时这里需要修改，比如多输入，多输出的情况
            y_pred = model(input_id)
            y_pred = y_pred.logits
            loss = torch.nn.CrossEntropyLoss(ignore_index=-1)(y_pred.view(-1, y_pred.shape[-1]), labels.view(-1))
            loss.backward()
            optimizer.step()
            train_loss.append(loss.item())
            if index % int(len(train_data) / 2) == 0:
                logger.info("batch loss %f" % loss)
        logger.info("epoch average loss: %f" % np.mean(train_loss))
        evaluator.eval(epoch)
    model_path = os.path.join(opt.model_path, "epoch_%d.pth" % epoch)
    torch.save(model.state_dict(), model_path)
    return model, train_data

if __name__ == "__main__":
    model, train_data = main(opt)
