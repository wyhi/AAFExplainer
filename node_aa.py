import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


# 这里考虑的都是同质图，因此bias实际上就是邻接矩阵
class GNN_AC(nn.Module):
    def __init__(self, in_dim, hidden_dim, dropout, activation, num_heads, cuda=False):
        super(GNN_AC, self).__init__()
        self.dropout = dropout
        self.attentions = [AttentionLayer(in_dim, hidden_dim, dropout, activation, cuda) for _ in range(num_heads)]

        for i, attention in enumerate(self.attentions):
            self.add_module('attention_{}'.format(i), attention)

    def forward(self, bias, emb_dest, emb_src, feature_src):
        adj = F.dropout(bias, self.dropout, training=self.training)
        x = torch.cat([att(adj, emb_dest, emb_src, feature_src).unsqueeze(0) for att in self.attentions], dim=0)

        return torch.mean(x, dim=0, keepdim=False)


class AttentionLayer(nn.Module):
    def __init__(self, in_dim, hidden_dim, dropout, activation, cuda=False):
        super(AttentionLayer, self).__init__()
        self.dropout = dropout
        self.activation = activation
        self.is_cuda = cuda

        self.W = nn.Parameter(nn.init.xavier_normal_(
            torch.Tensor(in_dim, hidden_dim).type(torch.cuda.FloatTensor if cuda else torch.FloatTensor),
            gain=np.sqrt(2.0)), requires_grad=True)
        self.W2 = nn.Parameter(nn.init.xavier_normal_(torch.Tensor(hidden_dim, hidden_dim).type(
            torch.cuda.FloatTensor if cuda else torch.FloatTensor), gain=np.sqrt(2.0)),
            requires_grad=True)

        self.leakyrelu = nn.LeakyReLU(0.2)

    def forward(self, bias, emb_dest, emb_src, feature_src):
        h_1 = torch.mm(emb_src, self.W)
        h_2 = torch.mm(emb_dest, self.W)

        e = self.leakyrelu(torch.mm(torch.mm(h_2, self.W2), h_1.t()))
        zero_vec = -9e15 * torch.ones_like(e)
        #  这里的e表示的是根据注意力获得的邻接矩阵的边的相似度（重要性分数）,bias过来给他抹去一些邻居
        attention = torch.where(bias > 0, e, zero_vec)
        attention = F.softmax(attention, dim=1)
        attention = F.dropout(attention, self.dropout, training=self.training)  # n*n
        # h_prime = torch.matmul(attention, feature_src)  # n*(feature的第二维)
        h_prime = torch.matmul(attention, h_1)  # n*(feature的第二维)

        return self.activation(h_prime)
