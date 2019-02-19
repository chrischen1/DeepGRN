import argparse
import numpy as np
import pandas as pd
from keras.callbacks import ModelCheckpoint, EarlyStopping, CSVLogger
from keras.optimizers import Adam
from keras.models import load_model
from pathlib import Path

import get_model
import utils

def make_argument_parser():

    parser = argparse.ArgumentParser(description="Train a model.",formatter_class=argparse.RawTextHelpFormatter)
    
    parser.add_argument('--data_dir', '-i', type=str, required=True,help='data_dir')
    parser.add_argument('--tf_name', '-t', type=str, required=True,help='tf_name')
    parser.add_argument('--output_dir', '-o', type=str, required=True,help='output_dir')

    parser.add_argument('--model_type', '-m', type=str, required=False,help='model_type',default='attention_after_lstm')
    parser.add_argument('--flanking', '-f', type=int, required=False,help='flanking',default=401)
    parser.add_argument('--val_chr', '-v', type=str, required=False,help='val_chr',default='chr11')
    parser.add_argument('--epochs', '-e', type=int, required=False,help='epochs',default=60)
    parser.add_argument('--patience', '-p', type=int, required=False,help='patience',default=5)
    parser.add_argument('--batch_size', '-s', type=int, required=False,help='batch_size',default=32)
    parser.add_argument('--learningrate', '-l', type=float, required=False,help='learningrate',default=0.001)
    parser.add_argument('--kernel_size', '-k', type=int, required=False,help='kernel_size',default=34)
    parser.add_argument('--num_filters', '-nf', type=int, required=False,help='num_filters',default=64)
    parser.add_argument('--num_recurrent', '-nr', type=int, required=False,help='num_recurrent',default=64)
    parser.add_argument('--num_dense', '-nd', type=int, required=False,help='num_dense',default=64)
    parser.add_argument('--dropout_rate', '-d', type=float, required=False,help='dropout_rate',default=0.1)
    parser.add_argument('--rnn_dropout', '-rd', type=float, required=False,help='rnn_dropout',default=0.1)
    parser.add_argument('--merge', '-me', type=str, required=False,help='merge method, max or ave',default='ave')
    parser.add_argument('--num_conv', '-nc', type=int, required=False,help='num_conv',default=1)
    parser.add_argument('--num_lstm', '-nl', type=int, required=False,help='num_lstm',default=1)
    parser.add_argument('--num_denselayer', '-dl', type=int, required=False,help='num_denselayer',default=1)
    parser.add_argument('--ratio_negative', '-rn', type=int, required=False,help='ratio_negative',default=1)
    
    parser.add_argument('--rnaseq', '-r', action='store_true',help='rnaseq')
    parser.add_argument('--gencode', '-g', action='store_true',help='gencode')
    parser.add_argument('--unique35', '-u', action='store_true',help='unique35')
    parser.add_argument('--use_peak', '-a', action='store_true',help='use_peak')
    parser.add_argument('--use_cudnn', '-c', action='store_true',help='use_cudnn')
    parser.add_argument('--single_attention_vector', '-sa', action='store_true',help='single_attention_vector')

    return parser

def main():
    parser = make_argument_parser()
    args = parser.parse_args()
    
    data_dir = args.data_dir
    tf_name = args.tf_name
    model_type = args.model_type
    flanking = args.flanking
    output_dir = args.output_dir
    val_chr = [args.val_chr]
    
    epochs = args.epochs
    patience = args.patience
    batch_size = args.batch_size
    learningrate = args.learningrate
    kernel_size = args.kernel_size
    num_filters = args.num_filters
    num_recurrent = args.num_recurrent
    num_dense = args.num_dense
    dropout_rate = args.dropout_rate
    rnn_dropout = args.rnn_dropout
    merge = args.merge
    
    num_conv = args.num_conv
    num_lstm = args.num_lstm
    num_denselayer = args.num_denselayer
    ratio_negative = args.ratio_negative
    
    rnaseq = args.rnaseq
    gencode = args.gencode
    unique35 = args.unique35
    
    use_peak = args.use_peak
    use_cudnn = args.use_cudnn
    single_attention_vector = args.single_attention_vector
    
    np.random.seed(2018)
    
    print(tf_name,model_type,flanking,rnaseq,gencode,unique35,output_dir)
    print(epochs,patience,batch_size,learningrate,kernel_size,num_filters,num_recurrent,num_dense,dropout_rate,merge)
    print(num_conv,num_lstm,num_denselayer,ratio_negative,use_peak,use_cudnn)
    
    genome_fasta_file = data_dir+'/hg19.genome.fa'
    DNase_path =data_dir+ '/DNase'
    bigwig_file_unique35 = data_dir + '/wgEncodeDukeMapabilityUniqueness35bp.bigWig'
    rnaseq_data_file = data_dir + '/rnaseq_data.csv'
    gencode_train_file = data_dir + '/gencode_feature_train.tsv'
    
    train_label_path = data_dir + '/label/train/'
    train_peaks_path = data_dir + '/label/train_positive/'
    
    output_model_path = output_dir
    output_history_path = output_dir
    
    label_data_file = train_label_path+tf_name+'.train.labels.tsv.gz'
    positive_peak_file = train_peaks_path+tf_name+'.train.peak.tsv'
    output_model = output_model_path + model_type + '.' + tf_name + '.'+'1'+ '.'+str(flanking)+'.unique35'+str(unique35)+ '.RNAseq'+str(rnaseq)+ '.Gencode'+str(gencode)+'.h5'
    output_history = output_history_path + model_type + '.' + tf_name + '.'+'1'+ '.'+str(flanking)+'.unique35'+str(unique35)+ '.RNAseq'+str(rnaseq)+ '.Gencode'+str(gencode)+'.csv'
    
    print('loading labels')
    all_chr,cell_list,train_region,val_region,train_label_data,val_label_data,train_label_unbind,val_label_unbind,train_idx,val_idx = utils.import_label(label_data_file)
    genome = utils.import_genome(genome_fasta_file,all_chr)
    window_size = train_region.stop[0]-train_region.start[0]
    
    num_meta = rnaseq_train = rnaseq_val = 0
    if rnaseq:
        rnaseq_data = pd.read_csv(rnaseq_data_file)
        rnaseq_train = rnaseq_data[cell_list].values
        rnaseq_val = rnaseq_data[cell_list].values
        num_meta = num_meta + 8
    else:
        rnaseq_train = rnaseq_val = 0
    
    if gencode:
        print('loading Gencode features')
        num_meta = num_meta + 6
        gencode_train,gencode_val = utils.import_gencode(gencode_train_file,train_idx,val_idx)
    else:
        gencode_train = gencode_val = 0
    
    #If model already exist, continue training
    module_outfile = Path(output_model)
    if module_outfile.is_file():
        model = load_model(output_model,custom_objects={'Attention1D': get_model.Attention1D})
    else:
        n_channel=6
        if not unique35:
            n_channel = 5
        model = get_model.make_model_attention(model_type=model_type,L=window_size+2*flanking,n_channel=n_channel, num_conv = num_conv,
                                               num_denselayer=num_denselayer,num_lstm=num_lstm,kernel_size=kernel_size,num_filters=num_filters, 
                                               num_recurrent=num_recurrent,num_dense=num_dense,dropout_rate = dropout_rate,
                                               rnn_dropout=rnn_dropout,num_meta=num_meta,merge=merge,cudnn=use_cudnn,
                                               single_attention_vector=single_attention_vector)
        model.compile(Adam(lr=learningrate),loss='binary_crossentropy',metrics=['accuracy'])
    
    if use_peak:
        label_bind = pd.read_csv(positive_peak_file,sep='\t')
        train_label_bind = label_bind[label_bind.chrom.isin(set(all_chr)-set(val_chr))]
        val_label_bind = label_bind[label_bind.chrom.isin(val_chr)]
        datagen_train = utils.TrainGeneratorSingle(genome,bigwig_file_unique35,DNase_path,train_region,train_label_bind,train_label_unbind,cell_list,rnaseq_train,gencode_train,True,unique35,rnaseq,gencode,flanking,batch_size,ratio_negative)
        datagen_val = utils.TrainGeneratorSingle(genome,bigwig_file_unique35,DNase_path,val_region,val_label_bind,val_label_unbind,cell_list,rnaseq_val,gencode_val,False,unique35,rnaseq,gencode,flanking,batch_size,ratio_negative)
    else:
        
        datagen_train = utils.DataGeneratorSingle(genome=genome,bw_dict_unique35=bigwig_file_unique35,DNase_path=DNase_path,
                                                  label_region=train_region,label_data=train_label_data,label_data_unbind=train_label_unbind,
                                                  cell_list=cell_list,rnaseq_data = rnaseq_train,gencode_data=gencode_train,
                                                  unique35=unique35,rnaseq=rnaseq,gencode=gencode,flanking=flanking,batch_size=batch_size,ratio_negative=ratio_negative)
        datagen_val = utils.DataGeneratorSingle(genome,bigwig_file_unique35,DNase_path,val_region,val_label_data,val_label_unbind,cell_list,rnaseq_val,gencode_val,unique35,rnaseq,gencode,flanking,batch_size,ratio_negative)
    
    checkpointer = ModelCheckpoint(filepath=output_model,verbose=1, save_best_only=True, monitor='val_acc')
    earlystopper = EarlyStopping(monitor='val_acc', patience=patience, verbose=1)
    csv_logger = CSVLogger(output_history,append=True)
    
    model.fit_generator(datagen_train,epochs=epochs,validation_data=datagen_val,callbacks=[checkpointer, earlystopper, csv_logger])

if __name__ == '__main__':
    main()